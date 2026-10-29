import uuid
from django.conf import settings
from django.db import models


class MessageLog(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        UNKNOWN = "unknown", "Unknown"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="message_logs"
    )
    reminder_job = models.ForeignKey(
        "reminders.ReminderJob",
        on_delete=models.PROTECT,
        related_name="message_logs",
        null=True,
        blank=True,
    )
    invoice = models.ForeignKey(
        "core.Invoice", on_delete=models.PROTECT, related_name="message_logs", null=True, blank=True
    )
    customer = models.ForeignKey(
        "core.Customer", on_delete=models.PROTECT, related_name="message_logs", null=True, blank=True
    )
    channel = models.CharField(max_length=16, choices=Channel.choices)
    provider = models.CharField(max_length=64)
    provider_message_id = models.CharField(max_length=255, blank=True)
    recipient = models.CharField(max_length=255)  # email address or phone number
    subject = models.CharField(max_length=998, blank=True)
    body_preview = models.CharField(max_length=200, blank=True)  # truncated, for logs
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.QUEUED
    )
    error_code = models.CharField(max_length=64, blank=True)
    error_detail = models.CharField(max_length=500, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    # Approval tracking
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_messages",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    queued_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-queued_at"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["provider_message_id"]),
        ]

    def __str__(self):
        return f"MessageLog {self.id} ({self.status})"
