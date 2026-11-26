from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.permissions import HasOrganizationAccess
from .models import Notification, NotificationPreference


# ---------------------------------------------------------------------------
# Enrichment helpers
# ---------------------------------------------------------------------------

def _step_label(step) -> str:
    """
    Return a human-readable label for a ReminderStep.
    E.g. "3 days after due", "2 days before due", "Day 7 from issue", "Step 2".
    """
    if step is None:
        return "Reminder"
    if step.offset_from_due is not None:
        n = step.offset_from_due
        if n >= 0:
            return f"{n} days after due"
        return f"{abs(n)} days before due"
    if step.offset_from_issue is not None:
        return f"Day {step.offset_from_issue} from issue"
    return f"Step {step.step_number}"


def _enrich_reminder_job(notification, org) -> dict:
    """
    Enrich a reminder_approval or reminder_failed notification by loading the
    linked ReminderJob. All lookups are org-scoped.
    """
    from reminders.models import ReminderJob

    job = ReminderJob.objects.select_related(
        "invoice", "customer", "step", "schedule"
    ).get(id=notification.entity_id, organization=org)

    return {
        "customer_name": job.customer.name,
        "invoice_number": job.invoice.invoice_number,
        "outstanding_minor": job.snapshot_outstanding_minor,
        "due_date": str(job.snapshot_due_date) if job.snapshot_due_date else None,
        "days_overdue": job.snapshot_days_overdue,
        "step_label": _step_label(job.step),
        "job_status": job.status,
        "block_reason": (
            job.block_reason
            if notification.event_type == Notification.EventType.REMINDER_FAILED
            else None
        ),
    }


def _enrich_import_batch(notification, org) -> dict:
    """
    Enrich an import_complete or import_failed notification by loading the
    linked ImportBatch. Org-scoped.
    """
    from imports_app.models import ImportBatch

    batch = ImportBatch.objects.get(id=notification.entity_id, organization=org)
    return {
        "file_name": batch.file_name,
        "batch_type": batch.batch_type,
        "rows_created": batch.rows_created,
        "rows_rejected": batch.rows_rejected,
        "status": batch.status,
    }


def _enrich_reconciliation_review(notification, org) -> dict:
    """
    Enrich a reconciliation_review notification with live unmatched /
    suggested counts. Org-scoped.
    """
    from reconciliation.models import BankTransaction, ReconciliationMatch

    unmatched_count = BankTransaction.objects.filter(
        organization=org,
        reconciliation_status=BankTransaction.ReconciliationStatus.UNMATCHED,
    ).count()

    suggested_count = ReconciliationMatch.objects.filter(
        organization=org,
        status=ReconciliationMatch.MatchStatus.SUGGESTED,
    ).count()

    return {
        "unmatched_count": unmatched_count,
        "suggested_count": suggested_count,
    }


def _enrich_notification(notification) -> dict:
    """
    Return a `details` dict for the given Notification instance.
    Never raises - returns {"error": "details_unavailable"} on lookup failure,
    and {} for types with no enrichment defined or with no entity reference.
    """
    org = notification.organization
    event = notification.event_type

    if event in (
        Notification.EventType.REMINDER_AWAITING_APPROVAL,
        Notification.EventType.REMINDER_FAILED,
    ):
        if not notification.entity_id:
            return {}
        try:
            return _enrich_reminder_job(notification, org)
        except Exception:
            return {"error": "details_unavailable"}

    if event in (
        Notification.EventType.IMPORT_COMPLETE,
        Notification.EventType.IMPORT_FAILED,
    ):
        if not notification.entity_id:
            return {}
        try:
            return _enrich_import_batch(notification, org)
        except Exception:
            return {"error": "details_unavailable"}

    if event == Notification.EventType.RECONCILIATION_REVIEW:
        try:
            return _enrich_reconciliation_review(notification, org)
        except Exception:
            return {"error": "details_unavailable"}

    # All other types (forecast_failed, security_event, membership_changed,
    # subscription_changed, payment_gateway): no enrichment yet
    return {}


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def notifications_list(request):
    """List notifications for the current user in the active organization."""
    org = request.membership.organization

    # Get base queryset (without slicing yet)
    base_qs = Notification.objects.filter(
        recipient=request.user,
        organization=org,
    )

    # Calculate unread count from base queryset (before slicing)
    unread_count = base_qs.filter(read_at__isnull=True).count()

    # Now get the limited list of notifications
    notifications = base_qs.order_by("-created_at")[:50]

    result = []
    for n in notifications:
        result.append({
            "id": str(n.id),
            "event_type": n.event_type,
            "entity_type": n.entity_type,
            "entity_id": n.entity_id,
            "payload": n.payload,
            "read": n.read_at is not None,
            "created_at": n.created_at.isoformat(),
            "details": _enrich_notification(n),
        })

    return Response({
        "unread_count": unread_count,
        "notifications": result,
    })


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def mark_read(request, notification_id):
    """Mark a single notification as read."""
    try:
        notif = Notification.objects.get(
            id=notification_id,
            recipient=request.user,
            organization=request.membership.organization,
        )
    except Notification.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if notif.read_at is None:
        notif.read_at = timezone.now()
        notif.save()
    return Response({"detail": "Marked as read."})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def mark_all_read(request):
    """Mark all unread notifications as read for the current user."""
    Notification.objects.filter(
        recipient=request.user,
        organization=request.membership.organization,
        read_at__isnull=True,
    ).update(read_at=timezone.now())
    return Response({"detail": "All notifications marked as read."})
