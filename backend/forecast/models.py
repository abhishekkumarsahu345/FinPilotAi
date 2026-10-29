import uuid
from django.db import models


class CashForecast(models.Model):
    class Scenario(models.TextChoices):
        CONSERVATIVE = "conservative", "Conservative"
        BASE = "base", "Base"
        OPTIMISTIC = "optimistic", "Optimistic"

    class Period(models.TextChoices):
        DAYS_7 = "7d", "7 Days"
        DAYS_30 = "30d", "30 Days"
        DAYS_60 = "60d", "60 Days"

    class TimingAssumption(models.TextChoices):
        DUE_DATE = "due_date", "Due Date (no adjustment)"
        HISTORICAL_DELAY = "historical_delay", "Historical Delay"
        CUSTOM_OFFSET = "custom_offset", "Custom Day Offset"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="cash_forecasts"
    )
    forecast_period = models.CharField(max_length=4, choices=Period.choices)
    scenario = models.CharField(max_length=16, choices=Scenario.choices)
    forecast_amount_minor = models.BigIntegerField()
    currency = models.CharField(max_length=3, default="INR")
    timing_assumption = models.CharField(
        max_length=24,
        choices=TimingAssumption.choices,
        default=TimingAssumption.DUE_DATE,
    )
    custom_offset_days = models.IntegerField(default=0)
    # Snapshot metadata
    qualifying_invoice_count = models.IntegerField(default=0)
    qualifying_invoice_ids = models.JSONField(default=list)
    assumptions_snapshot = models.JSONField(default=dict)
    insufficient_history = models.BooleanField(default=False)
    history_invoice_count = models.IntegerField(default=0)
    as_of_date = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["organization", "generated_at"]),
        ]

    def __str__(self):
        return f"Forecast {self.forecast_period} {self.scenario} ({self.organization})"


class ForecastLine(models.Model):
    """Individual invoice contribution to a forecast."""
    forecast = models.ForeignKey(
        CashForecast, on_delete=models.CASCADE, related_name="lines"
    )
    invoice = models.ForeignKey(
        "core.Invoice", on_delete=models.PROTECT, related_name="forecast_lines"
    )
    outstanding_balance_minor = models.BigIntegerField()
    due_date = models.DateField()
    expected_date = models.DateField()  # Due date + timing adjustment
    included = models.BooleanField(default=True)
    exclusion_reason = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["expected_date"]
