"""
Serializers for ReminderSchedule, ReminderStep, and enhanced ReminderJob APIs.
"""
from rest_framework import serializers
from .models import ReminderSchedule, ReminderStep, ReminderJob, ReminderTemplate


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
        offset_from_issue = data.get("offset_from_issue")
        offset_from_due = data.get("offset_from_due")
        if offset_from_issue is None and offset_from_due is None:
            raise serializers.ValidationError("Either offset_from_issue or offset_from_due must be set.")
        if offset_from_issue is not None and offset_from_due is not None:
            raise serializers.ValidationError("Only one of offset_from_issue or offset_from_due can be set, not both.")
        return data


class ReminderScheduleSerializer(serializers.ModelSerializer):
    step_count = serializers.SerializerMethodField()
    steps = serializers.SerializerMethodField()

    class Meta:
        model = ReminderSchedule
        fields = [
            "id", "name", "enabled", "is_default", "archived",
            "send_hour_start", "send_hour_end",
            "skip_weekdays", "excluded_customer_ids", "step_count", "steps",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "is_default", "archived", "created_at", "updated_at", "step_count", "steps"]

    def get_step_count(self, obj):
        return obj.steps.filter(enabled=True).count()

    def get_steps(self, obj):
        active_steps = obj.steps.filter(enabled=True).order_by("step_number")
        return ReminderStepSerializer(active_steps, many=True).data

    def create(self, validated_data):
        return ReminderSchedule.objects.create(
            organization=self.context["request"].membership.organization,
            created_by=self.context["request"].user,
            **validated_data,
        )

class ScheduleWithStepsSerializer(serializers.Serializer):
    """
    Create/update a ReminderSchedule together with its full step list in one request.

    Request body:
        {
            "name": "My Schedule",
            "steps": [
                {
                    "basis": "issue",
                    "kind": "on",
                    "days": 0,
                    "template": "<uuid>"
                }
            ]
        }

    Timing:
        basis=issue, days=N  -> N days after invoice issue date  (N >= 0)
        basis=due,   kind=on -> on the due date
        basis=due,   kind=before, days=N -> N days before due date (stored as -N)
        basis=due,   kind=after,  days=N -> N days after due date  (stored as +N)

    Approval mode is always MANUAL.
    """

    name = serializers.CharField(max_length=255, trim_whitespace=True)
    steps = serializers.ListField(
        child=serializers.DictField(), allow_empty=False, min_length=1, max_length=10
    )

    MAX_STEPS = 10
    MAX_DAYS = 365

    def validate_name(self, value):
        if not value:
            raise serializers.ValidationError("Schedule name is required.")
        return value

    def _validate_step(self, raw, index, org):
        prefix = "Step %d" % (index + 1)

        basis = raw.get("basis")
        if basis not in ("issue", "due"):
            raise serializers.ValidationError(
                {"steps.%d" % index: "%s: 'when to send' is missing or invalid." % prefix}
            )

        template_id = raw.get("template")
        if not template_id:
            raise serializers.ValidationError(
                {"steps.%d" % index: "%s: a message template must be selected." % prefix}
            )
        try:
            template = ReminderTemplate.objects.get(id=template_id, organization=org)
        except (ReminderTemplate.DoesNotExist, ValueError, TypeError):
            raise serializers.ValidationError(
                {"steps.%d" % index: "%s: the selected message template was not found." % prefix}
            )
        if template.channel != ReminderTemplate.Channel.EMAIL:
            raise serializers.ValidationError(
                {"steps.%d" % index: "%s: only email templates can be used right now." % prefix}
            )
        if not template.active:
            raise serializers.ValidationError(
                {"steps.%d" % index: "%s: that template is inactive." % prefix}
            )

        days_raw = raw.get("days", 0)
        try:
            days = int(days_raw)
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                {"steps.%d" % index: "%s: days must be a whole number." % prefix}
            )

        if basis == "issue":
            if not (0 <= days <= self.MAX_DAYS):
                raise serializers.ValidationError(
                    {"steps.%d" % index: "%s: days from invoice issue must be between 0 and %d." % (prefix, self.MAX_DAYS)}
                )
        else:
            kind = raw.get("kind", "on")
            if kind == "before":
                if days <= 0:
                    raise serializers.ValidationError(
                        {"steps.%d" % index: "%s: days before the due date must be at least 1." % prefix}
                    )
                if days > self.MAX_DAYS:
                    raise serializers.ValidationError(
                        {"steps.%d" % index: "%s: days before the due date cannot exceed %d." % (prefix, self.MAX_DAYS)}
                    )
                days = -days
            elif kind == "after":
                if days <= 0:
                    raise serializers.ValidationError(
                        {"steps.%d" % index: "%s: days after the due date must be at least 1." % prefix}
                    )
                if days > self.MAX_DAYS:
                    raise serializers.ValidationError(
                        {"steps.%d" % index: "%s: days after the due date cannot exceed %d." % (prefix, self.MAX_DAYS)}
                    )
            elif kind == "on":
                days = 0
            else:
                raise serializers.ValidationError(
                    {"steps.%d" % index: "%s: timing kind must be 'on', 'before', or 'after'." % prefix}
                )

        return {"basis": basis, "days": days, "template": template}

    def validate(self, data):
        org = self.context["organization"]
        raw_steps = data.get("steps", [])

        if not raw_steps:
            raise serializers.ValidationError({"steps": "A schedule needs at least one step."})
        if len(raw_steps) > self.MAX_STEPS:
            raise serializers.ValidationError(
                {"steps": "A schedule can have at most %d steps." % self.MAX_STEPS}
            )

        seen_keys = set()
        normalized = []
        for i, raw in enumerate(raw_steps):
            step = self._validate_step(raw, i, org)
            key = (step["basis"], step["days"])
            if key in seen_keys:
                human = self._timing_label(step["basis"], step["days"])
                raise serializers.ValidationError(
                    {"steps": "Two steps are both set to send %s. Each step must have a different timing." % human}
                )
            seen_keys.add(key)
            normalized.append(step)

        data["steps"] = normalized
        return data

    @staticmethod
    def _timing_label(basis, days):
        if basis == "issue":
            return "on the invoice issue date" if days == 0 else "%d days after invoice issue" % days
        if days == 0:
            return "on the due date"
        return "%d days %s the due date" % (abs(days), "before" if days < 0 else "after")

    @staticmethod
    def _derive_tone(basis, days):
        if basis == "issue":
            return ReminderStep.Tone.ISSUE
        if days < 0:
            return ReminderStep.Tone.FRIENDLY
        if days <= 7:
            return ReminderStep.Tone.GENTLE
        return ReminderStep.Tone.SERIOUS

    def create(self, validated_data):
        request = self.context["request"]
        org = self.context["organization"]
        user = request.user
        steps_data = validated_data["steps"]

        schedule = ReminderSchedule.objects.create(
            organization=org,
            name=validated_data["name"],
            enabled=True,
            send_hour_start=10,
            send_hour_end=18,
            skip_weekdays=[],
            excluded_customer_ids=[],
            created_by=user,
        )

        for i, s in enumerate(steps_data, start=1):
            ReminderStep.objects.create(
                schedule=schedule,
                step_number=i,
                offset_from_issue=(s["days"] if s["basis"] == "issue" else None),
                offset_from_due=(s["days"] if s["basis"] == "due" else None),
                tone=self._derive_tone(s["basis"], s["days"]),
                template=s["template"],
                approval_mode=ReminderStep.ApprovalMode.MANUAL,
                enabled=True,
                is_final_notice=(i == len(steps_data) and s["basis"] == "due" and s["days"] > 0),
            )

        return schedule

    def update_schedule(self, schedule):
        """
        Update name and replace the step list.
        Steps that keep the same (basis, days) timing retain their DB row,
        so existing ReminderJob FKs stay valid.
        Removed steps with live jobs are disabled (archived); those without are deleted.
        """
        validated = self.validated_data
        schedule.name = validated["name"]
        schedule.save(update_fields=["name", "updated_at"])

        steps_data = validated["steps"]
        existing = list(schedule.steps.all())

        remaining = []
        used_existing_ids = set()
        for s in steps_data:
            match = None
            for st in existing:
                if st.id in used_existing_ids:
                    continue
                if s["basis"] == "issue" and st.offset_from_issue == s["days"]:
                    match = st
                    break
                if s["basis"] == "due" and st.offset_from_due == s["days"]:
                    match = st
                    break
            if match:
                used_existing_ids.add(match.id)
            remaining.append(match)

        archive_number = 100
        for st in existing:
            if st.id in used_existing_ids:
                continue
            if st.jobs.filter(status__in=["proposed", "approved", "scheduled", "dispatched"]).exists():
                st.enabled = False
                st.step_number = archive_number
                archive_number += 1
                st.save(update_fields=["enabled", "step_number"])
            else:
                st.delete()

        for i, (s, st) in enumerate(zip(steps_data, remaining), start=1):
            final_notice = (i == len(steps_data) and s["basis"] == "due" and s["days"] > 0)
            if st is None:
                ReminderStep.objects.create(
                    schedule=schedule,
                    step_number=i,
                    offset_from_issue=(s["days"] if s["basis"] == "issue" else None),
                    offset_from_due=(s["days"] if s["basis"] == "due" else None),
                    tone=self._derive_tone(s["basis"], s["days"]),
                    template=s["template"],
                    approval_mode=ReminderStep.ApprovalMode.MANUAL,
                    enabled=True,
                    is_final_notice=final_notice,
                )
            else:
                st.step_number = i
                st.offset_from_issue = (s["days"] if s["basis"] == "issue" else None)
                st.offset_from_due = (s["days"] if s["basis"] == "due" else None)
                st.tone = self._derive_tone(s["basis"], s["days"])
                st.template = s["template"]
                st.enabled = True
                st.is_final_notice = final_notice
                st.save()

        return schedule

class EnhancedReminderJobSerializer(serializers.ModelSerializer):
    invoice_number = serializers.CharField(source="invoice.invoice_number", read_only=True)
    customer_name = serializers.CharField(source="customer.name", read_only=True)
    customer_email = serializers.CharField(source="customer.email", read_only=True)
    schedule_name = serializers.CharField(source="schedule.name", read_only=True)
    step_number = serializers.IntegerField(source="step.step_number", read_only=True)
    step_tone = serializers.CharField(source="step.tone", read_only=True)
    current_outstanding_minor = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    email_preview_subject = serializers.SerializerMethodField()
    email_preview_html = serializers.SerializerMethodField()

    class Meta:
        model = ReminderJob
        fields = [
            "id", "organization", "schedule", "schedule_name",
            "step", "step_number", "step_tone",
            "invoice", "invoice_number", "customer", "customer_name", "customer_email",
            "scheduled_date", "status", "status_display",
            "snapshot_total_minor", "snapshot_paid_minor", "snapshot_outstanding_minor",
            "snapshot_due_date", "snapshot_days_overdue", "snapshot_created_at",
            "sent_total_minor", "sent_paid_minor", "sent_outstanding_minor",
            "sent_due_date", "sent_days_overdue", "sent_html_body",
            "current_outstanding_minor", "balance_at_scheduling_minor",
            "approved_custom_intro", "approved_custom_closing",
            "needs_manual_followup",
            "approved_by", "approved_at", "rejected_by", "rejected_at",
            "dispatched_at", "block_reason", "retry_count",
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
        try:
            inv = obj.invoice
            active_paid = sum(a.amount_minor for a in inv.allocations.filter(reversed_at__isnull=True))
            return max(0, inv.total_minor - active_paid)
        except Exception:
            return None

    def get_email_preview_subject(self, obj):
        if obj.status not in [ReminderJob.Status.PROPOSED, ReminderJob.Status.APPROVED]:
            return obj.sent_html_body[:100] if obj.sent_html_body else None
        try:
            from reminders.email_rendering import build_invoice_context, generate_email_subject
            context = build_invoice_context(obj.invoice, obj.customer, obj.organization)
            tone = obj.step.tone if obj.step else "friendly"
            return generate_email_subject(context, tone)
        except Exception:
            return "Payment Reminder: Invoice %s" % obj.invoice.invoice_number

    def get_email_preview_html(self, obj):
        request = self.context.get("request")
        if not request or not request.query_params.get("include_preview"):
            return None
        if obj.status == ReminderJob.Status.DISPATCHED and obj.sent_html_body:
            return obj.sent_html_body
        try:
            from reminders.email_rendering import build_invoice_context, render_html_email_body
            context = build_invoice_context(obj.invoice, obj.customer, obj.organization)
            tone = obj.step.tone if obj.step else "friendly"
            return render_html_email_body(context, tone)
        except Exception as e:
            return "<p>Error generating preview: %s</p>" % str(e)


class ReminderJobApprovalSerializer(serializers.Serializer):
    custom_intro = serializers.CharField(required=False, allow_blank=True, max_length=2000)
    custom_closing = serializers.CharField(required=False, allow_blank=True, max_length=2000)