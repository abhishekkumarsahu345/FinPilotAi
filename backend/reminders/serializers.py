import re
from rest_framework import serializers
from .models import ReminderTemplate, ReminderTemplateRevision, ReminderPolicy, ReminderJob

SUPPORTED_PLACEHOLDERS = {
    "customer_name", "invoice_number", "invoice_date", "due_date",
    "outstanding_amount", "payment_reference_instructions", "business_contact",
}

CHANNEL_LIMITS = {
    "email": {"subject": 998, "body": 100_000},
    "whatsapp": {"subject": 0, "body": 4096},
}

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def validate_placeholders(subject: str, body: str, channel: str) -> list[str]:
    """Return list of error messages for invalid/oversized templates."""
    errors = []
    limits = CHANNEL_LIMITS.get(channel, CHANNEL_LIMITS["email"])

    # Length checks
    if subject and len(subject) > limits["subject"]:
        errors.append(f"Subject exceeds maximum length of {limits['subject']} characters for {channel}.")
    if len(body) > limits["body"]:
        errors.append(f"Body exceeds maximum length of {limits['body']} characters for {channel}.")

    # Placeholder checks
    all_tokens = set(PLACEHOLDER_RE.findall(subject + " " + body))
    unsupported = all_tokens - SUPPORTED_PLACEHOLDERS
    for tok in unsupported:
        errors.append(f"Unsupported placeholder: {{{{{tok}}}}}.")

    return errors


def render_template(subject: str, body: str, context: dict) -> tuple[str, str]:
    """Substitute placeholders. Raises ValueError if any placeholder is unresolvable."""
    def substitute(text):
        def replacer(m):
            key = m.group(1)
            if key not in context:
                raise ValueError(f"Unresolvable placeholder: {{{{{key}}}}}")
            # Basic HTML escaping for email safety
            value = str(context[key])
            return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return PLACEHOLDER_RE.sub(replacer, text)
    return substitute(subject), substitute(body)


class ReminderTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderTemplate
        fields = [
            "id", "name", "channel", "subject", "body",
            "active", "pending_revision", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "pending_revision", "created_at", "updated_at"]

    def validate(self, data):
        channel = data.get("channel", getattr(self.instance, "channel", "email"))
        subject = data.get("subject", getattr(self.instance, "subject", ""))
        body = data.get("body", getattr(self.instance, "body", ""))
        errors = validate_placeholders(subject, body, channel)
        if errors:
            raise serializers.ValidationError(errors)
        return data

    def create(self, validated_data):
        return ReminderTemplate.objects.create(
            organization=self.context["request"].membership.organization,
            created_by=self.context["request"].user,
            **validated_data,
        )

    def update(self, instance, validated_data):
        is_active_policy = instance.policies.filter(enabled=True).exists()
        body_changed = "body" in validated_data and validated_data["body"] != instance.body
        subject_changed = "subject" in validated_data and validated_data["subject"] != instance.subject

        if is_active_policy and (body_changed or subject_changed):
            # Save revision before applying change
            ReminderTemplateRevision.objects.create(
                template=instance,
                previous_subject=instance.subject,
                previous_body=instance.body,
                changed_by=self.context["request"].user,
            )
            validated_data["pending_revision"] = True

        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save()
        return instance


class ReminderTemplateRevisionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderTemplateRevision
        fields = ["id", "previous_subject", "previous_body", "changed_by", "created_at"]


class ReminderPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = ReminderPolicy
        fields = [
            "id", "name", "applicable_statuses", "trigger_offset_days", "channel",
            "template", "send_hour", "send_minute", "quiet_hours_start", "quiet_hours_end",
            "max_attempts", "min_days_between_reminders", "approval_mode",
            "excluded_customer_ids", "enabled", "created_at",
        ]
        read_only_fields = ["id", "approval_mode", "auto_mode_confirmed_by", "created_at"]

    def validate_trigger_offset_days(self, value):
        if not (-365 <= value <= 365):
            raise serializers.ValidationError("Trigger offset must be between -365 and 365.")
        return value

    def create(self, validated_data):
        # Default approval_mode is MANUAL — never AUTOMATIC on creation
        validated_data["approval_mode"] = ReminderPolicy.ApprovalMode.MANUAL
        return ReminderPolicy.objects.create(
            organization=self.context["request"].membership.organization,
            created_by=self.context["request"].user,
            **validated_data,
        )


class ReminderJobSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    policy_name = serializers.CharField(source="policy.name", read_only=True)
    balance_minor = serializers.SerializerMethodField()

    class Meta:
        model = ReminderJob
        fields = [
            "id", "policy", "policy_name", "invoice", "invoice_number",
            "customer", "customer_name", "scheduled_date", "status",
            "balance_at_scheduling_minor", "balance_minor",
            "approved_by", "approved_at", "rejected_at",
            "dispatched_at", "block_reason", "retry_count", "created_at",
        ]
        read_only_fields = [f.name for f in ReminderJob._meta.fields]

    def get_balance_minor(self, obj):
        """Current live balance — for comparison with scheduling-time snapshot."""
        from core.models import Invoice
        try:
            inv = obj.invoice
            active_paid = sum(
                a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
            )
            return max(0, inv.total_minor - active_paid)
        except Exception:
            return None
