"""
Authorized data-retrieval tools for the AI finance assistant.
All tools enforce organization and role permissions.
No tool modifies any financial record.
"""
from datetime import timedelta
from django.utils import timezone


def get_receivables_summary(org) -> dict:
    """Total outstanding, overdue, and due-soon amounts."""
    from core.models import Invoice
    today = timezone.localdate()
    invoices = (
        Invoice.objects.filter(organization=org, status=Invoice.Status.ISSUED)
        .prefetch_related("allocations")
    )
    outstanding = overdue = due_7 = 0
    for inv in invoices:
        bal = max(0, inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ))
        if not bal:
            continue
        outstanding += bal
        if inv.due_date < today:
            overdue += bal
        elif inv.due_date <= today + timedelta(days=7):
            due_7 += bal
    return {
        "as_of": str(today),
        "currency": org.default_currency,
        "outstanding_minor": outstanding,
        "overdue_minor": overdue,
        "due_next_7_days_minor": due_7,
    }


def get_top_overdue_customers(org, limit: int = 10) -> list:
    """Top customers by overdue amount."""
    from core.models import Invoice
    from collections import defaultdict
    today = timezone.localdate()
    invoices = (
        Invoice.objects.filter(organization=org, status=Invoice.Status.ISSUED)
        .select_related("customer")
        .prefetch_related("allocations")
    )
    cust_map = defaultdict(lambda: {"name": "", "overdue_minor": 0, "invoice_count": 0})
    for inv in invoices:
        if inv.due_date >= today:
            continue
        bal = max(0, inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ))
        if not bal:
            continue
        k = str(inv.customer_id)
        cust_map[k]["name"] = inv.customer.name
        cust_map[k]["overdue_minor"] += bal
        cust_map[k]["invoice_count"] += 1
    results = sorted(
        [{"customer_id": k, **v} for k, v in cust_map.items()],
        key=lambda x: x["overdue_minor"],
        reverse=True,
    )
    return results[:limit]


def get_invoices_due_range(org, days_from: int = 0, days_to: int = 7) -> list:
    """Invoices due within a date range."""
    from core.models import Invoice
    today = timezone.localdate()
    start = today + timedelta(days=days_from)
    end = today + timedelta(days=days_to)
    invoices = (
        Invoice.objects.filter(
            organization=org,
            status=Invoice.Status.ISSUED,
            due_date__gte=start,
            due_date__lte=end,
        )
        .select_related("customer")
        .prefetch_related("allocations")
        .order_by("due_date")
    )
    results = []
    for inv in invoices:
        bal = max(0, inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ))
        if bal:
            results.append({
                "invoice_number": inv.invoice_number,
                "customer_name": inv.customer.name,
                "due_date": str(inv.due_date),
                "outstanding_minor": bal,
            })
    return results


def get_late_paying_customers(org, min_invoices: int = 2) -> list:
    """Customers with a history of paying after the due date."""
    from core.models import Invoice, PaymentAllocation
    invoices = (
        Invoice.objects.filter(organization=org)
        .select_related("customer")
        .prefetch_related("allocations__payment")
    )
    from collections import defaultdict
    cust_delays = defaultdict(list)
    for inv in invoices:
        for alloc in inv.allocations.filter(reversed_at__isnull=True):
            if alloc.payment.payment_date and alloc.payment.payment_date > inv.due_date:
                delay = (alloc.payment.payment_date - inv.due_date).days
                cust_delays[str(inv.customer_id)].append(
                    (inv.customer.name, delay)
                )
    results = []
    for cust_id, entries in cust_delays.items():
        if len(entries) >= min_invoices:
            avg_delay = sum(d for _, d in entries) / len(entries)
            results.append({
                "customer_id": cust_id,
                "customer_name": entries[0][0],
                "late_payment_count": len(entries),
                "average_delay_days": round(avg_delay, 1),
            })
    return sorted(results, key=lambda x: x["average_delay_days"], reverse=True)


def get_forecast_summary(org, period_days: int = 30) -> dict:
    """Expected cash inflows for the given period."""
    from forecast.services import generate_forecast
    return generate_forecast(org, period_days)


AVAILABLE_TOOLS = {
    "get_receivables_summary": get_receivables_summary,
    "get_top_overdue_customers": get_top_overdue_customers,
    "get_invoices_due_range": get_invoices_due_range,
    "get_late_paying_customers": get_late_paying_customers,
    "get_forecast_summary": get_forecast_summary,
}
