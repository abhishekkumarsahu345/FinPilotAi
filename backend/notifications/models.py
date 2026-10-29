import uuid
from django.conf import settings
from django.db import models


class Notification(models.Model):
    class EventType(models.TextChoices):
        REMINDER_AWAITING_APPROVAL = "reminder_approval", "Reminder Awaiting Approval"
        REMINDER_FAILED = "reminder_failed", "Reminder Delivery Failed"
        IMPORT_COMPLETE = "import_complete", "Import Completed"
        IMPORT_FAILED = "import_failed", "Import Failed"
        RECONCILIATION_REVIEW = "reconciliation_review", "Reconciliation Requires Review"
        FORECAST_FAILED = "forecast_failed", "Forecast Generation Failed"
        SUBSCRIPTION_CHANGED = "subscription_changed", "Subscription Changed"
        SECURITY_EVENT = "security_event", "Security Event"
        MEMBERSHIP_CHANGED = "membership_changed", "Membership Changed"
        PAYMENT_GATEWAY_EVENT = "payment_gateway", "Payment Gateway Event"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization",
        on_delete=models.CASCADE,
        related_name="notifications",
        null=True,
        blank=True,
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    entity_type = models.CharField(max_length=64, blank=True)
    entity_id = models.CharField(max_length=80, blank=True)
    # Safe payload — no financial amounts, customer names, or references
    payload = models.JSONField(default=dict)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        # Deduplication: only one unread notification per event+entity+org
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "recipient", "event_type", "entity_type", "entity_id"],
                name="unique_unread_notification",
                condition=models.Q(read_at__isnull=True),
            )
        ]
        indexes = [
            models.Index(fields=["recipient", "read_at"]),
        ]

    def __str__(self):
        return f"Notification {self.event_type} for {self.recipient_id}"


class NotificationPreference(models.Model):
    """Per-user, per-org notification opt-in/out."""
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="notif_prefs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notif_prefs"
    )
    event_type = models.CharField(max_length=32)
    enabled = models.BooleanField(default=True)

    class Meta:
        unique_together = [("organization", "user", "event_type")]
