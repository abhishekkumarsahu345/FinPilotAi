"""
Authorized data-retrieval tools for the AI finance assistant.
All tools enforce organization and role permissions.
No tool modifies any financial record.

GENERAL-PURPOSE TOOL:
- query_data: Flexible querying with filters, aggregations, and grouping

SPECIFIC TOOLS:
- get_receivables_summary: High-level overview of outstanding amounts
- get_top_overdue_customers: Customers with highest overdue balances
- get_invoices_due_range: Invoices due within specific date range
- get_late_paying_customers: Customers with history of late payments
- get_forecast_summary: Expected cash inflows projection
- get_customer_details: Full details for a specific customer by name
- get_customer_invoices: All invoices for a specific customer
- get_customer_payments: Payment history for a specific customer
- get_invoice_details: Detailed invoice information by invoice number
- get_payment_details: Payment details by payment ID
- search_customers: Find customers by name (partial match)
- get_recent_activity: Latest transactions across organization
"""
from datetime import timedelta, datetime
from django.utils import timezone
from django.db.models import Q, Sum, Count, Avg, Max, Min, F
from django.db.models.functions import TruncMonth, TruncDate
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Entity and field allowlist for query_data tool
QUERY_DATA_SCHEMA = {
    "customers": {
        "model": "core.models.Customer",
        "fields": {
            "id": "UUID",
            "name": "Customer name",
            "contact_name": "Contact person name",
            "email": "Email address",
            "phone": "Phone number",
            "gstin": "GST identification number",
            "payment_terms_days": "Payment terms in days",
            "active": "Whether customer is active",
            "opt_out": "Whether customer opted out of reminders",
            "created_at": "Date created",
            "updated_at": "Date last updated",
        },
        "aggregates": ["count", "list"],
        "description": "Customers (also called persons, people, clients, parties, or debtors)"
    },
    "invoices": {
        "model": "core.models.Invoice",
        "fields": {
            "id": "UUID",
            "invoice_number": "Invoice number (e.g., INV-001)",
            "invoice_date": "Invoice date",
            "due_date": "Payment due date",
            "status": "Status (draft, issued, void)",
            "currency": "Currency code (INR)",
            "subtotal_minor": "Subtotal in paise (minor units)",
            "discount_minor": "Discount in paise",
            "tax_minor": "Tax in paise",
            "total_minor": "Total amount in paise",
            "source": "How invoice was created (manual, import, extraction)",
            "customer__name": "Customer name (related field)",
            "customer__id": "Customer ID (related field)",
            "created_at": "Date created",
            "updated_at": "Date last updated",
        },
        "aggregates": ["count", "sum", "avg", "min", "max", "list"],
        "description": "Invoices (also called bills)"
    },
    "payments": {
        "model": "core.models.Payment",
        "fields": {
            "id": "UUID",
            "payment_date": "Payment date",
            "amount_minor": "Amount in paise (minor units)",
            "currency": "Currency code (INR)",
            "method": "Payment method (bank_transfer, upi, cheque, cash, card, other)",
            "reference": "Payment reference/transaction ID",
            "status": "Status (active, reversed)",
            "source": "How payment was recorded",
            "customer__name": "Customer name (related field)",
            "customer__id": "Customer ID (related field)",
            "created_at": "Date recorded",
        },
        "aggregates": ["count", "sum", "avg", "min", "max", "list"],
        "description": "Payments received from customers"
    },
    "payment_allocations": {
        "model": "core.models.PaymentAllocation",
        "fields": {
            "id": "UUID",
            "amount_minor": "Allocated amount in paise",
            "reversed_at": "Date reversed (null if active)",
            "payment__id": "Payment ID",
            "payment__payment_date": "Payment date",
            "invoice__id": "Invoice ID",
            "invoice__invoice_number": "Invoice number",
            "created_at": "Date allocated",
        },
        "aggregates": ["count", "sum", "avg"],
        "description": "How payments are allocated to invoices"
    }
}

# Allowed operators for filters
ALLOWED_OPERATORS = {
    "eq": "__exact",  # Equal
    "ne": "__not",  # Not equal (custom handling)
    "gt": "__gt",  # Greater than
    "gte": "__gte",  # Greater than or equal
    "lt": "__lt",  # Less than
    "lte": "__lte",  # Less than or equal
    "contains": "__icontains",  # Contains (case-insensitive)
    "startswith": "__istartswith",  # Starts with (case-insensitive)
    "in": "__in",  # In list
    "isnull": "__isnull",  # Is null
}


def query_data(
    org,
    entity: str,
    fields: List[str] = None,
    filters: Dict[str, Any] = None,
    group_by: str = None,
    aggregates: Dict[str, str] = None,
    order_by: List[str] = None,
    limit: int = 100
) -> Dict[str, Any]:
    """
    General-purpose query tool for flexible data retrieval.
    
    This is the PRIMARY tool for counts, lists, filters, and aggregations.
    Use this instead of creating specific tools for every question type.
    
    Args:
        org: Organization instance (auto-injected)
        entity: Entity to query ("customers", "invoices", "payments", "payment_allocations")
        fields: List of fields to return (defaults to common fields if None)
        filters: Dict of filters, e.g., {"status": {"eq": "issued"}, "due_date": {"lt": "2024-12-31"}}
        group_by: Field to group by (e.g., "customer__name", "invoice_date__month")
        aggregates: Dict of aggregates, e.g., {"total": {"sum": "total_minor"}, "count": {"count": "*"}}
        order_by: List of fields to sort by (prefix with - for descending)
        limit: Max rows to return (default 100, max 200)
    
    Returns:
        {"rows": [...], "count": int, "filters_applied": {...}, "organization": str}
        
    Examples:
        - Count customers: query_data("customers", aggregates={"count": {"count": "*"}})
        - List active customers: query_data("customers", fields=["name", "email"], filters={"active": {"eq": True}})
        - Overdue invoices: query_data("invoices", filters={"status": {"eq": "issued"}, "due_date": {"lt": "today"}})
        - Top customers by invoice total: query_data("invoices", group_by="customer__name", 
          aggregates={"total": {"sum": "total_minor"}}, order_by=["-total"], limit=10)
        - Average invoice by month: query_data("invoices", group_by="invoice_date__month",
          aggregates={"avg": {"avg": "total_minor"}, "count": {"count": "*"}})
    
    Use when:
    - User asks "how many X", "list all X", "show X where Y"
    - User wants counts, averages, totals, min/max
    - User wants data grouped by customer, date, status, etc.
    - User wants top N, filtered lists, or custom queries
    
    Don't use when:
    - User wants detailed info about ONE specific record (use get_customer_details, get_invoice_details, etc.)
    - User wants complex calculations like aging reports or forecasts (use specialized tools)
    """
    from core.models import Customer, Invoice, Payment, PaymentAllocation
    
    # Validate entity
    if entity not in QUERY_DATA_SCHEMA:
        return {
            "error": "invalid_entity",
            "message": f"Entity '{entity}' not supported",
            "available_entities": list(QUERY_DATA_SCHEMA.keys())
        }
    
    schema = QUERY_DATA_SCHEMA[entity]
    
    # Get model
    model_map = {
        "customers": Customer,
        "invoices": Invoice,
        "payments": Payment,
        "payment_allocations": PaymentAllocation,
    }
    model = model_map[entity]
    
    # Start with org-filtered queryset
    qs = model.objects.filter(organization=org)
    
    # Apply filters
    filters = filters or {}
    applied_filters = {}
    
    for field, conditions in filters.items():
        # Validate field
        if field not in schema["fields"] and field != "id":
            logger.warning(f"Field '{field}' not in schema for {entity}, skipping")
            continue
        
        # Handle special date values
        if isinstance(conditions, dict):
            for op, value in conditions.items():
                if op not in ALLOWED_OPERATORS:
                    logger.warning(f"Operator '{op}' not allowed, skipping")
                    continue
                
                # Handle special values
                if value == "today":
                    value = timezone.localdate()
                elif value == "now":
                    value = timezone.now()
                elif isinstance(value, str) and value.startswith("today"):
                    # Handle "today-7" for 7 days ago
                    if "-" in value:
                        parts = value.split("-")
                        if len(parts) == 2 and parts[1].isdigit():
                            value = timezone.localdate() - timedelta(days=int(parts[1]))
                    elif "+" in value:
                        parts = value.split("+")
                        if len(parts) == 2 and parts[1].isdigit():
                            value = timezone.localdate() + timedelta(days=int(parts[1]))
                
                # Build Q object
                if op == "ne":
                    qs = qs.exclude(**{f"{field}": value})
                else:
                    lookup = f"{field}{ALLOWED_OPERATORS[op]}"
                    qs = qs.filter(**{lookup: value})
                
                applied_filters[field] = {op: str(value)}
    
    # Limit
    limit = min(limit, 200)
    
    # Handle aggregates + group_by
    if aggregates:
        agg_dict = {}
        for agg_name, agg_spec in aggregates.items():
            if not isinstance(agg_spec, dict) or len(agg_spec) != 1:
                continue
            
            agg_func, agg_field = list(agg_spec.items())[0]
            
            if agg_func == "count":
                agg_dict[agg_name] = Count("id")
            elif agg_func == "sum":
                agg_dict[agg_name] = Sum(agg_field)
            elif agg_func == "avg":
                agg_dict[agg_name] = Avg(agg_field)
            elif agg_func == "min":
                agg_dict[agg_name] = Min(agg_field)
            elif agg_func == "max":
                agg_dict[agg_name] = Max(agg_field)
        
        if group_by:
            # Group by query
            qs = qs.values(group_by).annotate(**agg_dict)
            if order_by:
                qs = qs.order_by(*order_by)
            rows = list(qs[:limit])
        else:
            # Single aggregate (no grouping)
            result = qs.aggregate(**agg_dict)
            rows = [result] if result else []
        
        return {
            "rows": rows,
            "count": len(rows),
            "filters_applied": applied_filters,
            "group_by": group_by,
            "aggregates": list(aggregates.keys()),
            "organization": org.name,
            "entity": entity
        }
    
    # Regular query (no aggregates)
    # Default fields if not specified
    if not fields:
        default_fields = {
            "customers": ["id", "name", "email", "active", "created_at"],
            "invoices": ["id", "invoice_number", "invoice_date", "due_date", "status", "total_minor", "customer__name"],
            "payments": ["id", "payment_date", "amount_minor", "method", "customer__name"],
            "payment_allocations": ["id", "amount_minor", "payment__payment_date", "invoice__invoice_number"],
        }
        fields = default_fields.get(entity, ["id"])
    
    # Validate fields
    valid_fields = []
    for field in fields:
        if field in schema["fields"] or field == "id" or "__" in field:  # Allow related fields
            valid_fields.append(field)
        else:
            logger.warning(f"Field '{field}' not in schema for {entity}, skipping")
    
    if not valid_fields:
        valid_fields = ["id"]
    
    # Select fields
    qs = qs.values(*valid_fields)
    
    # Order by
    if order_by:
        qs = qs.order_by(*order_by)
    
    # Get rows
    rows = list(qs[:limit])
    total_count = qs.count() if len(rows) == limit else len(rows)
    
    return {
        "rows": rows,
        "count": len(rows),
        "total_count": total_count,
        "fields": valid_fields,
        "filters_applied": applied_filters,
        "organization": org.name,
        "entity": entity,
        "limited": len(rows) == limit
    }


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



def get_customer_details(org, customer_name: str = None, customer_id: str = None) -> dict:
    """
    Get full details for a specific customer.
    
    Args:
        org: Organization instance
        customer_name: Customer name (exact match, case-insensitive)
        customer_id: Customer UUID (alternative to name)
    
    Returns:
        Customer details or error dict with candidates if ambiguous
        
    Use when: User asks "tell me about customer X", "show details for X"
    Don't use when: User wants a list of customers (use search_customers)
    """
    from core.models import Customer, Invoice
    
    if not customer_name and not customer_id:
        return {"error": "customer_name or customer_id required"}
    
    # Search by ID first (most specific)
    if customer_id:
        try:
            customer = Customer.objects.get(organization=org, id=customer_id)
        except Customer.DoesNotExist:
            return {"error": "customer_not_found", "customer_id": customer_id}
    else:
        # Search by exact name (case-insensitive)
        candidates = Customer.objects.filter(
            organization=org,
            name__iexact=customer_name
        )
        
        if candidates.count() == 0:
            # Try partial match to help user
            similar = Customer.objects.filter(
                organization=org,
                name__icontains=customer_name
            )[:5]
            
            if similar.exists():
                return {
                    "error": "customer_not_found_exact",
                    "query": customer_name,
                    "suggestions": [{"id": str(c.id), "name": c.name} for c in similar]
                }
            return {"error": "customer_not_found", "query": customer_name}
        
        elif candidates.count() > 1:
            # Multiple exact matches - return candidates
            return {
                "error": "ambiguous_customer",
                "query": customer_name,
                "candidates": [
                    {
                        "id": str(c.id),
                        "name": c.name,
                        "email": c.email,
                        "created_at": str(c.created_at.date())
                    }
                    for c in candidates
                ]
            }
        
        customer = candidates.first()
    
    # Get invoice statistics
    invoices = Invoice.objects.filter(
        organization=org,
        customer=customer
    )
    
    total_invoices = invoices.count()
    issued_invoices = invoices.filter(status=Invoice.Status.ISSUED)
    
    outstanding = 0
    overdue = 0
    today = timezone.localdate()
    
    for inv in issued_invoices.prefetch_related("allocations"):
        balance = max(0, inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ))
        if balance > 0:
            outstanding += balance
            if inv.due_date < today:
                overdue += balance
    
    return {
        "id": str(customer.id),
        "name": customer.name,
        "contact_name": customer.contact_name,
        "email": customer.email,
        "phone": customer.phone,
        "billing_address": customer.billing_address,
        "gstin": customer.gstin,
        "payment_terms_days": customer.payment_terms_days,
        "active": customer.active,
        "opt_out": customer.opt_out,
        "created_at": str(customer.created_at.date()),
        "notes": customer.notes[:200] if customer.notes else "",  # Limit notes length
        "statistics": {
            "total_invoices": total_invoices,
            "outstanding_minor": outstanding,
            "overdue_minor": overdue,
            "currency": org.default_currency
        }
    }


def get_customer_invoices(
    org,
    customer_name: str = None,
    customer_id: str = None,
    status: str = None,
    limit: int = 20
) -> dict:
    """
    Get all invoices for a specific customer.
    
    Args:
        org: Organization instance
        customer_name: Customer name (exact match)
        customer_id: Customer UUID (alternative to name)
        status: Filter by status (issued, draft, cancelled, paid)
        limit: Max invoices to return (default 20, max 100)
    
    Returns:
        List of invoices with balances
        
    Use when: User asks "show invoices for customer X", "what did X buy?"
    Don't use when: User wants invoices due soon (use get_invoices_due_range)
    """
    from core.models import Customer, Invoice
    
    limit = min(limit, 100)  # Cap at 100
    
    if not customer_name and not customer_id:
        return {"error": "customer_name or customer_id required"}
    
    # Find customer
    if customer_id:
        try:
            customer = Customer.objects.get(organization=org, id=customer_id)
        except Customer.DoesNotExist:
            return {"error": "customer_not_found", "customer_id": customer_id}
    else:
        try:
            customer = Customer.objects.get(organization=org, name__iexact=customer_name)
        except Customer.DoesNotExist:
            return {"error": "customer_not_found", "query": customer_name}
        except Customer.MultipleObjectsReturned:
            return {"error": "ambiguous_customer", "query": customer_name}
    
    # Get invoices
    invoices_qs = Invoice.objects.filter(
        organization=org,
        customer=customer
    ).prefetch_related("allocations").order_by("-invoice_date")
    
    if status:
        status_map = {
            "issued": Invoice.Status.ISSUED,
            "draft": Invoice.Status.DRAFT,
            "void": Invoice.Status.VOID,
        }
        if status.lower() in status_map:
            invoices_qs = invoices_qs.filter(status=status_map[status.lower()])
    
    invoices_qs = invoices_qs[:limit]
    
    results = []
    for inv in invoices_qs:
        paid = sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        )
        balance = max(0, inv.total_minor - paid)
        
        results.append({
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "invoice_date": str(inv.invoice_date),
            "due_date": str(inv.due_date),
            "status": inv.status,
            "total_minor": inv.total_minor,
            "paid_minor": paid,
            "balance_minor": balance,
            "currency": inv.currency
        })
    
    return {
        "customer_id": str(customer.id),
        "customer_name": customer.name,
        "invoice_count": len(results),
        "invoices": results
    }


def get_customer_payments(
    org,
    customer_name: str = None,
    customer_id: str = None,
    limit: int = 20
) -> dict:
    """
    Get payment history for a specific customer.
    
    Args:
        org: Organization instance
        customer_name: Customer name (exact match)
        customer_id: Customer UUID
        limit: Max payments to return (default 20, max 100)
    
    Returns:
        List of payments with allocations
        
    Use when: User asks "when did X pay?", "show payments from customer X"
    Don't use when: User wants general payment activity (use get_recent_activity)
    """
    from core.models import Customer, Payment
    
    limit = min(limit, 100)
    
    if not customer_name and not customer_id:
        return {"error": "customer_name or customer_id required"}
    
    # Find customer
    if customer_id:
        try:
            customer = Customer.objects.get(organization=org, id=customer_id)
        except Customer.DoesNotExist:
            return {"error": "customer_not_found", "customer_id": customer_id}
    else:
        try:
            customer = Customer.objects.get(organization=org, name__iexact=customer_name)
        except Customer.DoesNotExist:
            return {"error": "customer_not_found", "query": customer_name}
        except Customer.MultipleObjectsReturned:
            return {"error": "ambiguous_customer", "query": customer_name}
    
    # Get payments
    payments = Payment.objects.filter(
        organization=org,
        customer=customer
    ).prefetch_related("allocations__invoice").order_by("-payment_date")[:limit]
    
    results = []
    for pmt in payments:
        allocated = sum(
            a.amount_minor for a in pmt.allocations.filter(reversed_at__isnull=True)
        )
        unallocated = pmt.amount_minor - allocated
        
        allocations = [
            {
                "invoice_number": a.invoice.invoice_number,
                "amount_minor": a.amount_minor,
                "allocated_at": str(a.created_at.date()) if a.created_at else None
            }
            for a in pmt.allocations.filter(reversed_at__isnull=True)
        ]
        
        results.append({
            "id": str(pmt.id),
            "payment_date": str(pmt.payment_date),
            "amount_minor": pmt.amount_minor,
            "method": pmt.method,
            "reference": pmt.reference,
            "allocated_minor": allocated,
            "unallocated_minor": unallocated,
            "allocations": allocations,
            "currency": pmt.currency
        })
    
    return {
        "customer_id": str(customer.id),
        "customer_name": customer.name,
        "payment_count": len(results),
        "payments": results
    }


def get_invoice_details(org, invoice_number: str) -> dict:
    """
    Get detailed information for a specific invoice.
    
    Args:
        org: Organization instance
        invoice_number: Invoice number (e.g., "INV-001")
    
    Returns:
        Complete invoice details including line items and payments
        
    Use when: User asks "show invoice INV-001", "details of invoice X"
    Don't use when: User wants a list of invoices (use get_customer_invoices or get_invoices_due_range)
    """
    from core.models import Invoice
    
    try:
        invoice = Invoice.objects.select_related("customer").prefetch_related(
            "items", "allocations__payment"
        ).get(organization=org, invoice_number=invoice_number)
    except Invoice.DoesNotExist:
        return {"error": "invoice_not_found", "invoice_number": invoice_number}
    
    # Calculate payments
    payments = []
    paid_total = 0
    
    for alloc in invoice.allocations.filter(reversed_at__isnull=True):
        paid_total += alloc.amount_minor
        payments.append({
            "payment_id": str(alloc.payment.id),
            "payment_date": str(alloc.payment.payment_date),
            "amount_minor": alloc.amount_minor,
            "method": alloc.payment.method,
            "reference": alloc.payment.reference
        })
    
    balance = max(0, invoice.total_minor - paid_total)
    
    # Line items
    items = [
        {
            "description": item.description,
            "quantity": float(item.quantity),
            "unit_price_minor": item.unit_price_minor,
            "discount_minor": item.discount_minor,
            "line_total_minor": item.line_total_minor
        }
        for item in invoice.items.all()
    ]
    
    return {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "customer_id": str(invoice.customer.id),
        "customer_name": invoice.customer.name,
        "status": invoice.status,
        "invoice_date": str(invoice.invoice_date),
        "due_date": str(invoice.due_date),
        "currency": invoice.currency,
        "subtotal_minor": invoice.subtotal_minor,
        "discount_minor": invoice.discount_minor,
        "tax_minor": invoice.tax_minor,
        "total_minor": invoice.total_minor,
        "paid_minor": paid_total,
        "balance_minor": balance,
        "items": items,
        "payments": payments,
        "notes": invoice.notes[:200] if invoice.notes else ""
    }


def get_payment_details(org, payment_id: str) -> dict:
    """
    Get details for a specific payment.
    
    Args:
        org: Organization instance
        payment_id: Payment UUID
    
    Returns:
        Payment details with allocations
        
    Use when: User asks "show payment abc-123", "details of payment X"
    Don't use when: User wants payment history (use get_customer_payments)
    """
    from core.models import Payment
    
    try:
        payment = Payment.objects.select_related("customer").prefetch_related(
            "allocations__invoice"
        ).get(organization=org, id=payment_id)
    except Payment.DoesNotExist:
        return {"error": "payment_not_found", "payment_id": payment_id}
    
    allocated_total = 0
    allocations = []
    
    for alloc in payment.allocations.filter(reversed_at__isnull=True):
        allocated_total += alloc.amount_minor
        allocations.append({
            "invoice_id": str(alloc.invoice.id),
            "invoice_number": alloc.invoice.invoice_number,
            "amount_minor": alloc.amount_minor,
            "allocated_at": str(alloc.created_at.date()) if alloc.created_at else None
        })
    
    unallocated = payment.amount_minor - allocated_total
    
    return {
        "id": str(payment.id),
        "customer_id": str(payment.customer.id),
        "customer_name": payment.customer.name,
        "payment_date": str(payment.payment_date),
        "amount_minor": payment.amount_minor,
        "allocated_minor": allocated_total,
        "unallocated_minor": unallocated,
        "method": payment.method,
        "reference": payment.reference,
        "currency": payment.currency,
        "allocations": allocations,
        "notes": payment.notes[:200] if payment.notes else ""
    }


def search_customers(
    org,
    query: str,
    active_only: bool = True,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Search for customers by name (partial match).
    
    Args:
        org: Organization instance
        query: Search term (partial name match, case-insensitive)
        active_only: Only return active customers (default True)
        limit: Max results (default 20, max 100)
    
    Returns:
        List of matching customers with basic info
        
    Use when: User asks "find customers named X", "search for customer X", "show all customers"
    Don't use when: User wants specific customer details (use get_customer_details)
    """
    from core.models import Customer
    
    limit = min(limit, 100)
    
    customers_qs = Customer.objects.filter(
        organization=org,
        name__icontains=query
    )
    
    if active_only:
        customers_qs = customers_qs.filter(active=True)
    
    customers_qs = customers_qs.order_by("name")[:limit]
    
    results = [
        {
            "id": str(c.id),
            "name": c.name,
            "email": c.email,
            "phone": c.phone,
            "active": c.active,
            "created_at": str(c.created_at.date())
        }
        for c in customers_qs
    ]
    
    return results


def get_recent_activity(
    org,
    activity_type: str = "all",
    limit: int = 20
) -> dict:
    """
    Get recent financial activity across the organization.
    
    Args:
        org: Organization instance
        activity_type: "invoices", "payments", or "all" (default "all")
        limit: Max items per type (default 20, max 50)
    
    Returns:
        Recent invoices and/or payments
        
    Use when: User asks "what's new?", "recent activity", "latest transactions"
    Don't use when: User wants specific customer activity (use customer-specific tools)
    """
    from core.models import Invoice, Payment
    
    limit = min(limit, 50)
    result = {}
    
    if activity_type in ("all", "invoices"):
        recent_invoices = Invoice.objects.filter(
            organization=org
        ).select_related("customer").order_by("-created_at")[:limit]
        
        result["invoices"] = [
            {
                "invoice_number": inv.invoice_number,
                "customer_name": inv.customer.name,
                "status": inv.status,
                "total_minor": inv.total_minor,
                "due_date": str(inv.due_date),
                "created_at": str(inv.created_at.date())
            }
            for inv in recent_invoices
        ]
    
    if activity_type in ("all", "payments"):
        recent_payments = Payment.objects.filter(
            organization=org
        ).select_related("customer").order_by("-payment_date")[:limit]
        
        result["payments"] = [
            {
                "id": str(pmt.id),
                "customer_name": pmt.customer.name,
                "amount_minor": pmt.amount_minor,
                "method": pmt.method,
                "payment_date": str(pmt.payment_date),
                "recorded_at": str(pmt.created_at.date()) if pmt.created_at else None
            }
            for pmt in recent_payments
        ]
    
    return result


# Update AVAILABLE_TOOLS dictionary
AVAILABLE_TOOLS = {
    "query_data": query_data,
    "get_receivables_summary": get_receivables_summary,
    "get_top_overdue_customers": get_top_overdue_customers,
    "get_invoices_due_range": get_invoices_due_range,
    "get_late_paying_customers": get_late_paying_customers,
    "get_forecast_summary": get_forecast_summary,
    "get_customer_details": get_customer_details,
    "get_customer_invoices": get_customer_invoices,
    "get_customer_payments": get_customer_payments,
    "get_invoice_details": get_invoice_details,
    "get_payment_details": get_payment_details,
    "search_customers": search_customers,
    "get_recent_activity": get_recent_activity,
}


def get_schema_help() -> Dict[str, Any]:
    """
    Return schema information for the LLM to understand available entities and fields.
    
    This helps the LLM construct proper query_data calls.
    """
    return {
        "entities": {
            entity: {
                "description": schema["description"],
                "fields": schema["fields"],
                "aggregates_supported": schema["aggregates"]
            }
            for entity, schema in QUERY_DATA_SCHEMA.items()
        },
        "operators": {
            "eq": "Equal to",
            "ne": "Not equal to",
            "gt": "Greater than",
            "gte": "Greater than or equal",
            "lt": "Less than",
            "lte": "Less than or equal",
            "contains": "Contains (case-insensitive)",
            "startswith": "Starts with (case-insensitive)",
            "in": "In list",
            "isnull": "Is null/not null"
        },
        "special_values": {
            "today": "Current date",
            "now": "Current timestamp",
            "today-N": "N days ago (e.g., today-7)",
            "today+N": "N days from now (e.g., today+30)"
        }
    }


AVAILABLE_TOOLS["get_schema_help"] = get_schema_help
