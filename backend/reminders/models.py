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


class ReminderJob(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Awaiting Approval"
        APPROVED = "approved", "Approved"
        SCHEDULED = "scheduled", "Scheduled"
        DISPATCHED = "dispatched", "Dispatched"
        BLOCKED = "blocked", "Blocked"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reminder_jobs"
    )
    policy = models.ForeignKey(
        ReminderPolicy, on_delete=models.PROTECT, related_name="jobs"
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
    # Snapshot of outstanding balance at scheduling time for final-check comparison
    balance_at_scheduling_minor = models.BigIntegerField(default=0)
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
        # Prevent duplicate jobs for the same policy/invoice/date
        constraints = [
            models.UniqueConstraint(
                fields=["policy", "invoice", "scheduled_date"],
                name="unique_reminder_job_per_occurrence",
                condition=models.Q(status__in=["proposed", "approved", "scheduled", "dispatched"]),
            )
        ]
        ordering = ["-scheduled_date"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "invoice"]),
        ]

    def __str__(self):
        return f"ReminderJob {self.id} ({self.status})"
