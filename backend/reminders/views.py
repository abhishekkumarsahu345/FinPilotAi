from django.db import transaction
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from core.models import AuditLog
from core.permissions import HasOrganizationAccess, FINANCE_ROLES

from .models import ReminderTemplate, ReminderPolicy, ReminderJob, ReminderSchedule, ReminderStep
from .serializers import (
    ReminderTemplateSerializer, ReminderPolicySerializer, ReminderJobSerializer,
)
from .schedule_serializers import (
    ReminderScheduleSerializer, ReminderStepSerializer,
    EnhancedReminderJobSerializer, ReminderJobApprovalSerializer,
)


class ReminderTemplateViewSet(viewsets.ModelViewSet):
    serializer_class = ReminderTemplateSerializer
    permission_classes = [permissions.IsAuthenticated, HasOrganizationAccess]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return ReminderTemplate.objects.filter(
            organization=self.request.membership.organization
        )

    @action(detail=True, methods=["post"], url_path="approve-revision")
    def approve_revision(self, request, pk=None):
        template = self.get_object()
        if not template.pending_revision:
            return Response({"detail": "No pending revision for this template."})
        if request.membership.role not in FINANCE_ROLES:
            return Response(
                {"detail": "Only Finance Manager or Business Owner can approve revisions."},
                status=status.HTTP_403_FORBIDDEN,
            )
        with transaction.atomic():
            template.pending_revision = False
            template.save()
            AuditLog.objects.create(
                organization=template.organization,
                actor=request.user,
                action="template.revision_approved",
                entity_type="reminder_template",
                entity_id=str(template.id),
                summary=f"Approved revision for template {template.name}",
            )
        return Response({"detail": "Revision approved."})


class ReminderPolicyViewSet(viewsets.ModelViewSet):
    serializer_class = ReminderPolicySerializer
    permission_classes = [permissions.IsAuthenticated, HasOrganizationAccess]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return ReminderPolicy.objects.filter(
            organization=self.request.membership.organization
        ).select_related("template")

    def perform_update(self, serializer):
        instance = serializer.save()
        AuditLog.objects.create(
            organization=instance.organization,
            actor=self.request.user,
            action="policy.updated",
            entity_type="reminder_policy",
            entity_id=str(instance.id),
            summary=f"Updated reminder policy {instance.name}",
        )

    @action(detail=True, methods=["post"], url_path="activate-auto")
    def activate_auto(self, request, pk=None):
        """
        Explicitly activate automatic sending mode.
        Requires body: {"confirm": true}
        """
        policy = self.get_object()
        if request.membership.role not in FINANCE_ROLES:
            return Response(
                {"detail": "Only Finance Manager or Business Owner can activate automatic mode."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not request.data.get("confirm") is True:
            return Response(
                {"detail": "Automatic mode requires explicit confirmation. Send {'confirm': true}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            policy.approval_mode = ReminderPolicy.ApprovalMode.AUTOMATIC
            policy.auto_mode_confirmed_by = request.user
            policy.save()
            AuditLog.objects.create(
                organization=policy.organization,
                actor=request.user,
                action="policy.auto_mode_activated",
                entity_type="reminder_policy",
                entity_id=str(policy.id),
                summary=f"Activated automatic sending for policy {policy.name}",
            )
        return Response({"detail": "Automatic sending mode activated."})

    @action(detail=True, methods=["post"], url_path="deactivate-auto")
    def deactivate_auto(self, request, pk=None):
        policy = self.get_object()
        with transaction.atomic():
            policy.approval_mode = ReminderPolicy.ApprovalMode.MANUAL
            policy.auto_mode_confirmed_by = None
            policy.save()
            AuditLog.objects.create(
                organization=policy.organization,
                actor=request.user,
                action="policy.auto_mode_deactivated",
                entity_type="reminder_policy",
                entity_id=str(policy.id),
                summary=f"Deactivated automatic sending for policy {policy.name}",
            )
        return Response({"detail": "Automatic sending mode deactivated."})


class ReminderJobViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReminderJobSerializer
    permission_classes = [permissions.IsAuthenticated, HasOrganizationAccess]
    filterset_fields = {"status": ["exact"], "invoice": ["exact"], "policy": ["exact"]}
    ordering_fields = ["scheduled_date", "created_at"]

    def get_queryset(self):
        return (
            ReminderJob.objects.filter(organization=self.request.membership.organization)
            .select_related("policy", "invoice__customer", "customer")
            .prefetch_related("invoice__allocations")
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        job = self.get_object()
        if job.status != ReminderJob.Status.PROPOSED:
            return Response(
                {"detail": f"Job is in status '{job.status}', not 'proposed'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.membership.role not in FINANCE_ROLES:
            return Response(
                {"detail": "Only Finance Manager or Business Owner can approve reminders."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Final eligibility check before approval
        inv = job.invoice
        active_paid = sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        )
        balance = max(0, inv.total_minor - active_paid)

        if balance == 0 or inv.status in (inv.Status.PAID if hasattr(inv.Status, "PAID") else [], "void"):
            job.status = ReminderJob.Status.BLOCKED
            job.block_reason = "Invoice has been paid or voided since job was created."
            job.save()
            return Response({"detail": job.block_reason}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            job.status = ReminderJob.Status.APPROVED
            job.approved_by = request.user
            job.approved_at = timezone.now()
            job.save()
            AuditLog.objects.create(
                organization=job.organization,
                actor=request.user,
                action="reminder_job.approved",
                entity_type="reminder_job",
                entity_id=str(job.id),
                summary=f"Approved reminder job for invoice {inv.invoice_number}",
            )

        # Dispatch asynchronously if messaging is configured
        try:
            from messaging.tasks import dispatch_reminder_job
            dispatch_reminder_job.delay(str(job.id))
        except Exception:
            pass  # Will be picked up by worker when configured

        return Response({"detail": "Reminder approved and queued for dispatch."})

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        job = self.get_object()
        if job.status not in (ReminderJob.Status.PROPOSED, ReminderJob.Status.SCHEDULED):
            return Response(
                {"detail": f"Cannot reject a job in status '{job.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            job.status = ReminderJob.Status.REJECTED
            job.rejected_by = request.user
            job.rejected_at = timezone.now()
            job.save()
            AuditLog.objects.create(
                organization=job.organization,
                actor=request.user,
                action="reminder_job.rejected",
                entity_type="reminder_job",
                entity_id=str(job.id),
                summary=f"Rejected reminder job for invoice {job.invoice.invoice_number}",
            )
        return Response({"detail": "Reminder rejected."})


# ── New Schedule/Step System ViewSets ──────────────────────────────────────


class ReminderScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = ReminderScheduleSerializer
    permission_classes = [permissions.IsAuthenticated, HasOrganizationAccess]
    http_method_names = ["get", "post", "put", "patch", "head", "options", "delete"]

    def get_queryset(self):
        return ReminderSchedule.objects.filter(
            organization=self.request.membership.organization
        ).prefetch_related("steps")

    def perform_create(self, serializer):
        schedule = serializer.save()
        AuditLog.objects.create(
            organization=schedule.organization,
            actor=self.request.user,
            action="reminder_schedule.created",
            entity_type="reminder_schedule",
            entity_id=str(schedule.id),
            summary=f"Created reminder schedule: {schedule.name}",
        )

    def perform_update(self, serializer):
        schedule = serializer.save()
        AuditLog.objects.create(
            organization=schedule.organization,
            actor=self.request.user,
            action="reminder_schedule.updated",
            entity_type="reminder_schedule",
            entity_id=str(schedule.id),
            summary=f"Updated reminder schedule: {schedule.name}",
        )

    def perform_destroy(self, instance):
        AuditLog.objects.create(
            organization=instance.organization,
            actor=self.request.user,
            action="reminder_schedule.deleted",
            entity_type="reminder_schedule",
            entity_id=str(instance.id),
            summary=f"Deleted reminder schedule: {instance.name}",
        )
        instance.delete()


class ReminderStepViewSet(viewsets.ModelViewSet):
    serializer_class = ReminderStepSerializer
    permission_classes = [permissions.IsAuthenticated, HasOrganizationAccess]
    http_method_names = ["get", "post", "put", "patch", "head", "options", "delete"]

    def get_queryset(self):
        return ReminderStep.objects.filter(
            schedule__organization=self.request.membership.organization
        ).select_related("schedule", "template")

    def perform_create(self, serializer):
        step = serializer.save()
        AuditLog.objects.create(
            organization=step.schedule.organization,
            actor=self.request.user,
            action="reminder_step.created",
            entity_type="reminder_step",
            entity_id=str(step.id),
            summary=f"Created reminder step {step.step_number} for schedule {step.schedule.name}",
        )

    def perform_update(self, serializer):
        step = serializer.save()
        AuditLog.objects.create(
            organization=step.schedule.organization,
            actor=self.request.user,
            action="reminder_step.updated",
            entity_type="reminder_step",
            entity_id=str(step.id),
            summary=f"Updated reminder step {step.step_number}",
        )

    def perform_destroy(self, instance):
        AuditLog.objects.create(
            organization=instance.schedule.organization,
            actor=self.request.user,
            action="reminder_step.deleted",
            entity_type="reminder_step",
            entity_id=str(instance.id),
            summary=f"Deleted reminder step {instance.step_number} from schedule {instance.schedule.name}",
        )
        instance.delete()

    @action(detail=True, methods=["post"], url_path="activate-auto")
    def activate_auto(self, request, pk=None):
        """Enable automatic sending for this step (requires confirmation)."""
        step = self.get_object()
        if request.membership.role not in FINANCE_ROLES:
            return Response(
                {"detail": "Only Finance Manager or Business Owner can activate automatic mode."},
                status=status.HTTP_403_FORBIDDEN,
            )
        if not request.data.get("confirm") is True:
            return Response(
                {"detail": "Automatic mode requires explicit confirmation. Send {'confirm': true}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            step.approval_mode = ReminderStep.ApprovalMode.AUTOMATIC
            step.auto_mode_confirmed_by = request.user
            step.save()
            AuditLog.objects.create(
                organization=step.schedule.organization,
                actor=request.user,
                action="reminder_step.auto_mode_activated",
                entity_type="reminder_step",
                entity_id=str(step.id),
                summary=f"Activated automatic sending for step {step.step_number}",
            )
        return Response({"detail": "Automatic sending mode activated for this step."})

    @action(detail=True, methods=["post"], url_path="deactivate-auto")
    def deactivate_auto(self, request, pk=None):
        """Disable automatic sending for this step."""
        step = self.get_object()
        with transaction.atomic():
            step.approval_mode = ReminderStep.ApprovalMode.MANUAL
            step.auto_mode_confirmed_by = None
            step.save()
            AuditLog.objects.create(
                organization=step.schedule.organization,
                actor=request.user,
                action="reminder_step.auto_mode_deactivated",
                entity_type="reminder_step",
                entity_id=str(step.id),
                summary=f"Deactivated automatic sending for step {step.step_number}",
            )
        return Response({"detail": "Automatic sending mode deactivated for this step."})


class EnhancedReminderJobViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Enhanced reminder job viewset with preview support and approval workflow.
    Use ?include_preview=true to get email HTML in responses.
    """
    serializer_class = EnhancedReminderJobSerializer
    permission_classes = [permissions.IsAuthenticated, HasOrganizationAccess]
    filterset_fields = {
        "status": ["exact", "in"],
        "invoice": ["exact"],
        "schedule": ["exact"],
        "step": ["exact"],
        "needs_manual_followup": ["exact"],
    }
    ordering_fields = ["scheduled_date", "created_at", "snapshot_days_overdue"]

    def get_queryset(self):
        return (
            ReminderJob.objects.filter(organization=self.request.membership.organization)
            .select_related(
                "schedule", "step__template", "invoice__customer", "customer",
                "approved_by", "rejected_by"
            )
            .prefetch_related("invoice__items", "invoice__allocations__payment")
        )

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        """Approve a reminder job and dispatch email."""
        job = self.get_object()
        
        if job.status != ReminderJob.Status.PROPOSED:
            return Response(
                {"detail": f"Job is in status '{job.status}', not 'proposed'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        if request.membership.role not in FINANCE_ROLES:
            return Response(
                {"detail": "Only Finance Manager or Business Owner can approve reminders."},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Validate custom messages if provided
        serializer = ReminderJobApprovalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Final eligibility check before approval
        inv = job.invoice
        active_paid = sum(
            a.amount_minor for a in inv.allocations.filter(reversed_at__isnull=True)
        )
        balance = max(0, inv.total_minor - active_paid)

        if balance == 0:
            job.status = ReminderJob.Status.BLOCKED
            job.block_reason = "Invoice has been fully paid since job was created."
            job.save()
            return Response({"detail": job.block_reason}, status=status.HTTP_400_BAD_REQUEST)

        if inv.status == "void":
            job.status = ReminderJob.Status.BLOCKED
            job.block_reason = "Invoice has been voided."
            job.save()
            return Response({"detail": job.block_reason}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            job.status = ReminderJob.Status.APPROVED
            job.approved_by = request.user
            job.approved_at = timezone.now()
            job.approved_custom_intro = serializer.validated_data.get("custom_intro", "")
            job.approved_custom_closing = serializer.validated_data.get("custom_closing", "")
            job.save()
            
            AuditLog.objects.create(
                organization=job.organization,
                actor=request.user,
                action="reminder_job.approved",
                entity_type="reminder_job",
                entity_id=str(job.id),
                summary=f"Approved reminder for invoice {inv.invoice_number}",
            )

        # Dispatch asynchronously
        try:
            from reminders.dispatch_tasks import dispatch_reminder_email
            dispatch_reminder_email.delay(str(job.id))
        except Exception:
            pass  # Will be picked up when worker is running

        return Response({
            "detail": "Reminder approved and queued for dispatch.",
            "job_id": str(job.id),
        })

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        """Reject a reminder job."""
        job = self.get_object()
        
        if job.status not in (ReminderJob.Status.PROPOSED, ReminderJob.Status.SCHEDULED):
            return Response(
                {"detail": f"Cannot reject a job in status '{job.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        with transaction.atomic():
            job.status = ReminderJob.Status.REJECTED
            job.rejected_by = request.user
            job.rejected_at = timezone.now()
            job.save()
            
            AuditLog.objects.create(
                organization=job.organization,
                actor=request.user,
                action="reminder_job.rejected",
                entity_type="reminder_job",
                entity_id=str(job.id),
                summary=f"Rejected reminder for invoice {job.invoice.invoice_number}",
            )
        
        return Response({"detail": "Reminder rejected."})

    @action(detail=True, methods=["post"])
    def mark_for_followup(self, request, pk=None):
        """Mark a reminder for manual followup."""
        job = self.get_object()
        
        with transaction.atomic():
            job.needs_manual_followup = True
            job.save()
            
            AuditLog.objects.create(
                organization=job.organization,
                actor=request.user,
                action="reminder_job.marked_for_followup",
                entity_type="reminder_job",
                entity_id=str(job.id),
                summary=f"Marked reminder for invoice {job.invoice.invoice_number} for manual followup",
            )
        
        return Response({"detail": "Marked for manual followup."})
