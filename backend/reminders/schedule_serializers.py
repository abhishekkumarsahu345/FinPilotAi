"""
Serializers for ReminderSchedule, ReminderStep, and enhanced ReminderJob APIs.
"""
from rest_framework import serializers
from .models import ReminderSchedule, ReminderStep, ReminderJob, ReminderTemplate


class ReminderScheduleSerializer(serializers.ModelSerializer):
    step_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ReminderSchedule
        fields = [
            "id", "name", "enabled", "send_hour_start", "send_hour_end",
            "skip_weekdays", "excluded_customer_ids", "step_count",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at", "step_count"]
    
    def get_step_count(self, obj):
        return obj.steps.count()
    
    def create(self, validated_data):
        return ReminderSchedule.objects.create(
            organization=self.context["request"].membership.organization,
            created_by=self.context["request"].user,
            **validated_data,
        )


class ReminderStepSerializer(serializers.ModelSerializer):
    template_name = serializers.CharField(source="template.name", read_only=True)
    tone_display = serializers.CharField(source="get_tone_display", read_only=True)
    approval_mode_display = serializers.CharField(source="get_approval_mode_display", read_only=True)
    
    class Meta:
        model = ReminderStep
        fields = [
            "id", "schedule", "step_number", "offset_from_issue", "offset_from_due",
            "tone", "tone_display", "template", "template_name",
            "approval_mode", "approval_mode_display",
            "auto_mode_confirmed_by", "enabled", "is_final_notice",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "template_name", "tone_display", "approval_mode_display"]
    
    def validate(self, data):
        # Ensure exactly one offset is set
        offset_from_issue = data.get("offset_from_issue")
        offset_from_due = data.get("offset_from_due")
        
        if offset_from_issue is None and offset_from_due is None:
            raise serializers.ValidationError(
                "Either offset_from_issue or offset_from_due must be set."
            )
        if offset_from_issue is not None and offset_from_due is not None:
            raise serializers.ValidationError(
                "Only one of offset_from_issue or offset_from_due can be set, not both."
            )
        
        return data


class EnhancedReminderJobSerializer(serializers.ModelSerializer):
    """
    Enhanced serializer with snapshot data, payment details, and preview support.
    """
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    schedule_name = serializers.CharField(source="schedule.name", read_only=True)
    step_number = serializers.IntegerField(source="step.step_number", read_only=True)
    step_tone = serializers.CharField(source="step.tone", read_only=True)
    
    # Computed fields
    current_outstanding_minor = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    # Preview data
    email_preview_subject = serializers.SerializerMethodField()
    email_preview_html = serializers.SerializerMethodField()
    
    class Meta:
        model = ReminderJob
        fields = [
            "id", "organization", "schedule", "schedule_name",
            "step", "step_number", "step_tone",
            "invoice", "invoice_number", "customer", "customer_name", "customer_email",
            "scheduled_date", "status", "status_display",
            
            # Snapshot data
            "snapshot_total_minor", "snapshot_paid_minor", "snapshot_outstanding_minor",
            "snapshot_due_date", "snapshot_days_overdue", "snapshot_created_at",
            
            # Sent data
            "sent_total_minor", "sent_paid_minor", "sent_outstanding_minor",
            "sent_due_date", "sent_days_overdue", "sent_html_body",
            
            # Current vs snapshot comparison
            "current_outstanding_minor", "balance_at_scheduling_minor",
            
            # Custom edits
            "approved_custom_intro", "approved_custom_closing",
            "needs_manual_followup",
            
            # Workflow
            "approved_by", "approved_at", "rejected_by", "rejected_at",
            "dispatched_at", "block_reason", "retry_count",
            
            # Preview
            "email_preview_subject", "email_preview_html",
            
            "created_at",
        ]
        read_only_fields = [
            "id", "organization", "invoice", "customer", "scheduled_date",
            "snapshot_total_minor", "snapshot_paid_minor", "snapshot_outstanding_minor",
            "snapshot_due_date", "snapshot_days_overdue", "snapshot_created_at",
            "sent_total_minor", "sent_paid_minor", "sent_outstanding_minor",
            "sent_due_date", "sent_days_overdue", "sent_html_body",
            "balance_at_scheduling_minor", "current_outstanding_minor",
            "approved_by", "approved_at", "rejected_by", "rejected_at",
            "dispatched_at", "block_reason", "retry_count", "created_at",
            "invoice_number", "customer_name", "customer_email",
            "schedule_name", "step_number", "step_tone", "status_display",
            "email_preview_subject", "email_preview_html",
        ]
    
    def get_current_outstanding_minor(self, obj):
        """Calculate live outstanding balance."""
        try:
            inv = obj.invoice
            active_paid = sum(
                a.amount_minor for a in inv.allocations.filter(reversed_at__isnull=True)
            )
            return max(0, inv.total_minor - active_paid)
        except Exception:
            return None
    
    def get_email_preview_subject(self, obj):
        """Generate preview subject line."""
        if obj.status not in [ReminderJob.Status.PROPOSED, ReminderJob.Status.APPROVED]:
            return obj.sent_html_body[:100] if obj.sent_html_body else None
        
        try:
            from reminders.email_rendering import build_invoice_context, generate_email_subject
            context = build_invoice_context(obj.invoice, obj.customer, obj.organization)
            tone = obj.step.tone if obj.step else 'friendly'
            return generate_email_subject(context, tone)
        except Exception:
            return f"Payment Reminder: Invoice {obj.invoice.invoice_number}"
    
    def get_email_preview_html(self, obj):
        """Generate HTML preview. Only included if ?include_preview=true in request."""
        request = self.context.get("request")
        if not request or not request.query_params.get("include_preview"):
            return None
        
        if obj.status == ReminderJob.Status.DISPATCHED and obj.sent_html_body:
            return obj.sent_html_body
        
        try:
            from reminders.email_rendering import build_invoice_context, render_html_email_body
            context = build_invoice_context(obj.invoice, obj.customer, obj.organization)
            tone = obj.step.tone if obj.step else 'friendly'
            return render_html_email_body(context, tone)
        except Exception as e:
            return f"<p>Error generating preview: {str(e)}</p>"


class ReminderJobApprovalSerializer(serializers.Serializer):
    """Serializer for approval actions with optional custom message."""
    custom_intro = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    custom_closing = serializers.CharField(required=False, allow_blank=True, max_length=2000)
