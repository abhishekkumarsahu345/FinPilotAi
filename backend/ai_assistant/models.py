import uuid
from django.conf import settings
from django.db import models


class AIRun(models.Model):
    """Metadata-only log of AI assistant usage — no question/answer content."""
    class TaskType(models.TextChoices):
        FINANCE_QUERY = "finance_query", "Finance Query"
        DOCUMENT_EXTRACTION = "document_extraction", "Document Extraction"

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        PERMISSION_DENIED = "permission_denied", "Permission Denied"
        UNAVAILABLE = "unavailable", "Service Unavailable"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="ai_runs"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ai_runs"
    )
    session_id = models.CharField(max_length=64, blank=True)
    task_type = models.CharField(max_length=32, choices=TaskType.choices)
    provider = models.CharField(max_length=64, blank=True)
    model_identifier = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=24, choices=Status.choices)
    # Tool calls made (list of tool names, no data)
    tool_calls = models.JSONField(default=list)
    # Token usage metadata
    prompt_tokens = models.IntegerField(default=0)
    completion_tokens = models.IntegerField(default=0)
    error_category = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["user", "created_at"]),
        ]
