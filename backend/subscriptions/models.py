import uuid
from django.db import models


class Plan(models.Model):
    """Central plan definitions — readable at runtime, no hardcoding."""
    class Tier(models.TextChoices):
        STARTER = "starter", "Starter"
        GROWTH = "growth", "Growth"
        BUSINESS = "business", "Business"
        ENTERPRISE = "enterprise", "Enterprise"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tier = models.CharField(max_length=16, choices=Tier.choices, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    # Usage limits (0 = unlimited)
    max_users = models.IntegerField(default=0)
    max_invoices_per_month = models.IntegerField(default=0)
    max_messages_per_month = models.IntegerField(default=0)
    max_ai_requests_per_month = models.IntegerField(default=0)
    # Pricing (stored for reference; billing managed externally)
    price_monthly_minor = models.BigIntegerField(default=0)
    price_annually_minor = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="INR")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_monthly_minor"]

    def __str__(self):
        return self.name


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = "trial", "Trial"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past Due"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="subscriptions"
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.TRIAL)
    billing_provider_reference = models.CharField(max_length=255, blank=True)
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.organization} — {self.plan} ({self.status})"


class BillingEvent(models.Model):
    """Immutable billing history."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="billing_events"
    )
    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.PROTECT,
        related_name="billing_events",
        null=True,
        blank=True,
    )
    event_type = models.CharField(max_length=64)
    provider_event_id = models.CharField(max_length=255, blank=True, unique=True)
    amount_minor = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="INR")
    description = models.CharField(max_length=500, blank=True)
    raw_payload = models.JSONField(default=dict)  # Provider webhook payload
    processed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-processed_at"]
