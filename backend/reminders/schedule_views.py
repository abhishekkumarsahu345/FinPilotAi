"""
Views for the new ReminderSchedule and ReminderStep system.
"""
from django.db import transaction
from django.utils import timezone

from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.models import AuditLog
from core.permissions import HasOrganizationAccess, FINANCE_ROLES

from .models import ReminderSchedule, ReminderStep, ReminderJob
from .schedule_serializers import (
    ReminderScheduleSerializer, ReminderStepSerializer,
    EnhancedReminderJobSerializer, ReminderJobApprovalSerializer,
)


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
