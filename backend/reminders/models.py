import uuid
from django.conf import settings
from django.db import models


class ReminderTemplate(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reminder_templates"
    )
    name = models.CharField(max_length=255)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.EMAIL)
    subject = models.CharField(max_length=998, blank=True)  # email subject line
    body = models.TextField()
    active = models.BooleanField(default=True)
    # Revision control
    pending_revision = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.channel})"


class ReminderTemplateRevision(models.Model):
    """Immutable version history for template changes."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        ReminderTemplate, on_delete=models.CASCADE, related_name="revisions"
    )
    previous_subject = models.CharField(max_length=998, blank=True)
    previous_body = models.TextField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="template_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ReminderPolicy(models.Model):
    class ApprovalMode(models.TextChoices):
        MANUAL = "manual", "Approval Required"
        AUTOMATIC = "automatic", "Automatic"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reminder_policies"
    )
    name = models.CharField(max_length=255)
    # Which invoice statuses this policy applies to (JSON list of status strings)
    applicable_statuses = models.JSONField(default=list)
    # Days relative to due date: negative = before, positive = after
    trigger_offset_days = models.IntegerField(default=0)
    channel = models.CharField(
        max_length=16, choices=Channel.choices, default=Channel.EMAIL
    )
    template = models.ForeignKey(
        ReminderTemplate,
        on_delete=models.PROTECT,
        related_name="policies",
    )
    # Scheduling
    send_hour = models.PositiveSmallIntegerField(default=9)  # 24h local time
    send_minute = models.PositiveSmallIntegerField(default=0)
    quiet_hours_start = models.PositiveSmallIntegerField(null=True, blank=True)
    quiet_hours_end = models.PositiveSmallIntegerField(null=True, blank=True)
    # Limits
    max_attempts = models.PositiveSmallIntegerField(default=3)
    min_days_between_reminders = models.PositiveSmallIntegerField(default=7)
    # Mode
    approval_mode = models.CharField(
        max_length=16, choices=ApprovalMode.choices, default=ApprovalMode.MANUAL
    )
    auto_mode_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_auto_policies",
    )
    # Customer-level exclusions (JSON list of customer UUIDs as strings)
    excluded_customer_ids = models.JSONField(default=list)
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_policies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.organization})"


class ReminderDefaultTemplate(models.Model):
    """
    Shipped default templates for each tone. Read-only reference.
    Organizations copy these when creating their first policy.
    """
    class Tone(models.TextChoices):
        FRIENDLY = "friendly", "Friendly Reminder"
        FIRM = "firm", "Firm Notice"
        FINAL = "final", "Final Notice"
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tone = models.CharField(max_length=16, choices=Tone.choices, unique=True)
    channel = models.CharField(max_length=16, default="email")
    subject = models.CharField(max_length=998)
    body = models.TextField()
    
    class Meta:
        ordering = ["tone"]
    
    def __str__(self):
        return f"Default: {self.tone}"


class ReminderSchedule(models.Model):
    """
    Container for a multi-step reminder lifecycle tied to an organization.
    Defines global settings like business hours and customer exclusions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reminder_schedules"
    )
    name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    # Business hours for sending (local org time)
    send_hour_start = models.PositiveSmallIntegerField(default=10)  # 10 AM
    send_hour_end = models.PositiveSmallIntegerField(default=18)    # 6 PM
    # Skip sending on specific weekdays (0=Monday, 6=Sunday)
    skip_weekdays = models.JSONField(default=list)  # e.g., [5, 6] = skip Sat/Sun
    # Customer-level exclusions (JSON list of customer UUIDs as strings)
    excluded_customer_ids = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_schedules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.organization})"


class ReminderStep(models.Model):
    """
    Individual reminder stage within a schedule.
    Each step has exactly one trigger offset (either from invoice issue or due date).
    """
    class Tone(models.TextChoices):
        ISSUE = "issue", "Invoice Issue Notification"
        FRIENDLY = "friendly", "Friendly Reminder"
        GENTLE = "gentle", "Gentle Reminder"
        SERIOUS = "serious", "Serious Notice"

    class ApprovalMode(models.TextChoices):
        MANUAL = "manual", "Approval Required"
        AUTOMATIC = "automatic", "Automatic"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.ForeignKey(
        ReminderSchedule, on_delete=models.CASCADE, related_name="steps"
    )
    step_number = models.PositiveSmallIntegerField()  # 1, 2, 3, 4...
    # Offset triggers (exactly one must be set, enforced by CHECK constraint)
    offset_from_issue = models.IntegerField(null=True, blank=True)  # Days from invoice_date
    offset_from_due = models.IntegerField(null=True, blank=True)    # Days from due_date (negative=before, positive=after)
    tone = models.CharField(max_length=16, choices=Tone.choices, default=Tone.FRIENDLY)
    template = models.ForeignKey(
        ReminderTemplate, on_delete=models.PROTECT, related_name="steps"
    )
    approval_mode = models.CharField(
        max_length=16, choices=ApprovalMode.choices, default=ApprovalMode.MANUAL
    )
    auto_mode_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_auto_steps",
    )
    enabled = models.BooleanField(default=True)
    is_final_notice = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["step_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "step_number"],
                name="unique_step_number_per_schedule",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(offset_from_due__isnull=True, offset_from_issue__isnull=False)
                    | models.Q(offset_from_due__isnull=False, offset_from_issue__isnull=True)
                ),
                name="step_has_exactly_one_offset",
            ),
        ]

    def __str__(self):
        offset = self.offset_from_due if self.offset_from_due is not None else self.offset_from_issue
        ref = "due" if self.offset_from_due is not None else "issue"
        return f"Step {self.step_number}: {offset} days from {ref}"


class ReminderJob(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Awaiting Approval"
        APPROVED = "approved", "Approved"
        SCHEDULED = "scheduled", "Scheduled"
        DISPATCHED = "dispatched", "Dispatched"
        BLOCKED = "blocked", "Blocked"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped (date passed)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reminder_jobs"
    )
    # Link to either old policy system OR new schedule/step system
    policy = models.ForeignKey(
        ReminderPolicy, on_delete=models.PROTECT, related_name="jobs",
        null=True, blank=True
    )
    schedule = models.ForeignKey(
        ReminderSchedule, on_delete=models.PROTECT, related_name="jobs",
        null=True, blank=True
    )
    step = models.ForeignKey(
        ReminderStep, on_delete=models.PROTECT, related_name="jobs",
        null=True, blank=True
    )
    invoice = models.ForeignKey(
        "core.Invoice", on_delete=models.PROTECT, related_name="reminder_jobs"
    )
    customer = models.ForeignKey(
        "core.Customer", on_delete=models.PROTECT, related_name="reminder_jobs"
    )
    scheduled_date = models.DateField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.PROPOSED
    )
    # Snapshot of invoice financial state at scheduling time
    balance_at_scheduling_minor = models.BigIntegerField(default=0)
    snapshot_total_minor = models.BigIntegerField(default=0)
    snapshot_paid_minor = models.BigIntegerField(default=0)
    snapshot_outstanding_minor = models.BigIntegerField(default=0)
    snapshot_due_date = models.DateField(null=True, blank=True)
    snapshot_days_overdue = models.IntegerField(default=0)
    snapshot_created_at = models.DateTimeField(null=True, blank=True)
    
    # Actually sent financial data (populated when dispatched)
    sent_total_minor = models.BigIntegerField(null=True, blank=True)
    sent_paid_minor = models.BigIntegerField(null=True, blank=True)
    sent_outstanding_minor = models.BigIntegerField(null=True, blank=True)
    sent_due_date = models.DateField(null=True, blank=True)
    sent_days_overdue = models.IntegerField(null=True, blank=True)
    sent_html_body = models.TextField(blank=True)
    
    # Custom edits by approver
    approved_custom_intro = models.TextField(blank=True)
    approved_custom_closing = models.TextField(blank=True)
    
    # Manual followup flag
    needs_manual_followup = models.BooleanField(default=False)
    
    idempotency_key = models.CharField(max_length=128, unique=True)
    # Approval
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_jobs",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    # Rejection
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rejected_jobs",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    # Dispatch
    dispatched_at = models.DateTimeField(null=True, blank=True)
    block_reason = models.CharField(max_length=500, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Prevent duplicate jobs for the same schedule/step/invoice
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "step", "invoice"],
                name="unique_reminder_job_per_step_invoice",
                condition=models.Q(status__in=["proposed", "approved", "scheduled", "dispatched"]),
            )
        ]
        ordering = ["-scheduled_date"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "invoice"]),
            models.Index(fields=["organization", "needs_manual_followup"]),
        ]

    def __str__(self):
        return f"ReminderJob {self.id} ({self.status})"
