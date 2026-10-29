import uuid
from django.conf import settings
from django.db import models


class ImportBatch(models.Model):
    class BatchType(models.TextChoices):
        INVOICE = "invoice", "Invoice Import"
        BANK_STATEMENT = "bank_statement", "Bank Statement Import"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        PREVIEW_READY = "preview_ready", "Preview Ready"
        COMMITTED = "committed", "Committed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="import_batches"
    )
    batch_type = models.CharField(max_length=20, choices=BatchType.choices)
    file_reference = models.CharField(max_length=500, blank=True)  # S3 key
    file_name = models.CharField(max_length=255, blank=True)
    file_hash = models.CharField(max_length=64, blank=True)  # SHA-256
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    rows_total = models.IntegerField(default=0)
    rows_valid = models.IntegerField(default=0)
    rows_created = models.IntegerField(default=0)
    rows_rejected = models.IntegerField(default=0)
    rows_skipped = models.IntegerField(default=0)
    rows_flagged = models.IntegerField(default=0)
    error_summary = models.TextField(blank=True)
    # Column mapping for bank statements (JSON)
    column_mapping = models.JSONField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="import_batches",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # Prevent duplicate file imports per organization
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "file_hash", "batch_type"],
                name="unique_batch_per_org_file",
                condition=models.Q(file_hash__gt=""),
            )
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.batch_type} batch {self.id} ({self.status})"


class ImportRow(models.Model):
    class RowStatus(models.TextChoices):
        VALID = "valid", "Valid"
        ERROR = "error", "Error"
        DUPLICATE = "duplicate", "Duplicate Flagged"
        SKIPPED = "skipped", "Skipped"
        COMMITTED = "committed", "Committed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(
        ImportBatch, on_delete=models.CASCADE, related_name="rows"
    )
    row_number = models.PositiveIntegerField()
    raw_data = models.JSONField()  # Original parsed row
    normalized_data = models.JSONField(null=True, blank=True)  # After normalization
    status = models.CharField(
        max_length=16, choices=RowStatus.choices, default=RowStatus.VALID
    )
    errors = models.JSONField(default=list)  # List of {field, message}
    warnings = models.JSONField(default=list)  # Non-blocking warnings
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["row_number"]
        unique_together = [("batch", "row_number")]

    def __str__(self):
        return f"Row {self.row_number} of {self.batch_id} ({self.status})"
