import uuid
from django.conf import settings
from django.db import models


class BankTransaction(models.Model):
    class ReconciliationStatus(models.TextChoices):
        UNMATCHED = "unmatched", "Unmatched"
        SUGGESTED = "suggested", "Suggestion Pending"
        CONFIRMED = "confirmed", "Confirmed"
        EXCLUDED = "excluded", "Excluded"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="bank_transactions"
    )
    import_batch = models.ForeignKey(
        "imports_app.ImportBatch",
        on_delete=models.PROTECT,
        related_name="bank_transactions",
    )
    transaction_date = models.DateField()
    value_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    transaction_reference = models.CharField(max_length=255, blank=True)
    account_identifier = models.CharField(max_length=100, blank=True)
    debit_minor = models.BigIntegerField(default=0)
    credit_minor = models.BigIntegerField(default=0)
    currency = models.CharField(max_length=3, default="INR")
    # Running total of confirmed allocations (must not exceed credit_minor)
    allocated_minor = models.BigIntegerField(default=0)
    reconciliation_status = models.CharField(
        max_length=16,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.UNMATCHED,
    )
    is_probable_duplicate = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-transaction_date"]
        indexes = [
            models.Index(fields=["organization", "reconciliation_status"]),
            models.Index(fields=["organization", "transaction_date"]),
        ]

    def available_minor(self):
        """Amount available for further allocation."""
        return max(0, self.credit_minor - self.allocated_minor)

    def __str__(self):
        return f"Txn {self.id} {self.transaction_date} +{self.credit_minor}"


class ReconciliationMatch(models.Model):
    class MatchStatus(models.TextChoices):
        SUGGESTED = "suggested", "Suggested"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        DEFERRED = "deferred", "Deferred"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reconciliation_matches"
    )
    transaction = models.ForeignKey(
        BankTransaction, on_delete=models.PROTECT, related_name="matches"
    )
    # Match can point to an invoice (direct) or an existing payment record
    invoice = models.ForeignKey(
        "core.Invoice",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reconciliation_matches",
    )
    payment = models.ForeignKey(
        "core.Payment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reconciliation_matches",
    )
    suggested_amount_minor = models.BigIntegerField()
    # Confidence and evidence
    confidence_score = models.FloatField(default=0.0)  # 0.0–1.0
    match_evidence = models.JSONField(default=list)  # List of {signal, detail}
    is_deterministic = models.BooleanField(default=False)  # True = exact-rule match
    status = models.CharField(
        max_length=16, choices=MatchStatus.choices, default=MatchStatus.SUGGESTED
    )
    # Confirmed allocation linkage
    payment_allocation = models.ForeignKey(
        "core.PaymentAllocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciliation_matches",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_matches",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-confidence_score"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["transaction", "status"]),
        ]

    def __str__(self):
        return f"Match {self.id} ({self.status}, confidence={self.confidence_score:.2f})"
