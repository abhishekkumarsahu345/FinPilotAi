"""
Cash inflow forecasting service.
Deterministic, explainable — no AI involved.
All amounts are integer Minor_Units (paise).
"""
from datetime import date, timedelta
from statistics import mean
from typing import Any

from django.utils import timezone

from core.models import Invoice, Payment, PaymentAllocation
from .models import CashForecast, ForecastLine

MIN_HISTORY_COUNT = 10  # Minimum paid invoices needed for historical delay


def _get_active_balance(inv: Invoice) -> int:
    return max(
        0,
        inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ),
    )


def _payment_delays(org, as_of: date, months: int = 12) -> list[int]:
    """
    Compute historical payment delays (days) for the organisation.
    Returns list of integers (positive = paid late, negative = paid early).
    Only uses invoices paid within the last `months` months.
    """
    cutoff = as_of - timedelta(days=months * 30)
    delays = []
    # Find invoices that have been fully paid
    invoices = (
        Invoice.objects.filter(
            organization=org,
            status=Invoice.Status.ISSUED,
            invoice_date__gte=cutoff,
        )
        .prefetch_related("allocations")
    )
    for inv in invoices:
        balance = _get_active_balance(inv)
        if balance > 0:
            continue  # Not fully paid
        # Find the latest allocation date as the effective payment date
        latest_alloc = (
            inv.allocations.filter(reversed_at__isnull=True)
            .order_by("-created_at")
            .first()
        )
        if latest_alloc and latest_alloc.payment.payment_date:
            delay = (latest_alloc.payment.payment_date - inv.due_date).days
            delays.append(delay)
    return delays


def generate_forecast(
    org,
    period_days: int,
    timing_assumption: str = "due_date",
    custom_offset_days: int = 0,
) -> dict[str, Any]:
    """
    Generate three forecast scenarios for the given period.
    Returns dict with scenario data and contributing invoice lines.
    """
    as_of = timezone.localdate()
    cutoff = as_of + timedelta(days=period_days)

    # Get qualifying invoices (issued, non-zero balance, non-void, non-draft)
    invoices = (
        Invoice.objects.filter(
            organization=org,
            status=Invoice.Status.ISSUED,
        )
        .select_related("customer")
        .prefetch_related("allocations__payment")
    )

    qualifying = []
    for inv in invoices:
        balance = _get_active_balance(inv)
        if balance <= 0:
            continue
        qualifying.append((inv, balance))

    # Compute historical delays
    history_delays = _payment_delays(org, as_of)
    has_sufficient_history = len(history_delays) >= MIN_HISTORY_COUNT

    # Determine adjustment per scenario
    if has_sufficient_history and timing_assumption == "historical_delay":
        sorted_delays = sorted(history_delays)
        n = len(sorted_delays)
        conservative_offset = sorted_delays[int(n * 0.75)]  # 75th percentile (more delay)
        base_offset = int(mean(sorted_delays))
        optimistic_offset = sorted_delays[int(n * 0.25)]  # 25th percentile (less delay)
    elif timing_assumption == "custom_offset":
        conservative_offset = custom_offset_days + 14
        base_offset = custom_offset_days
        optimistic_offset = custom_offset_days - 7
    else:
        # Fallback / due_date: use rule-based offsets
        conservative_offset = 14  # assume late
        base_offset = 0
        optimistic_offset = -7  # assume slightly early

    assumptions = {
        "timing_assumption": timing_assumption,
        "sufficient_history": has_sufficient_history,
        "history_invoice_count": len(history_delays),
        "conservative_offset_days": conservative_offset,
        "base_offset_days": base_offset,
        "optimistic_offset_days": optimistic_offset,
        "as_of": str(as_of),
        "period_days": period_days,
    }

    scenarios = {}
    for scenario_name, offset in [
        ("conservative", conservative_offset),
        ("base", base_offset),
        ("optimistic", optimistic_offset),
    ]:
        total = 0
        lines = []
        for inv, balance in qualifying:
            expected_date = inv.due_date + timedelta(days=offset)
            included = as_of <= expected_date <= cutoff
            line = {
                "invoice_id": str(inv.id),
                "invoice_number": inv.invoice_number,
                "customer_name": inv.customer.name,
                "due_date": str(inv.due_date),
                "expected_date": str(expected_date),
                "outstanding_balance_minor": balance,
                "included": included,
                "exclusion_reason": "" if included else f"Expected date {expected_date} outside forecast window {as_of}–{cutoff}",
            }
            if included:
                total += balance
            lines.append(line)
        scenarios[scenario_name] = {"total_minor": total, "lines": lines}

    return {
        "as_of": str(as_of),
        "period_days": period_days,
        "currency": org.default_currency,
        "insufficient_history": not has_sufficient_history,
        "assumptions": assumptions,
        "scenarios": scenarios,
    }
