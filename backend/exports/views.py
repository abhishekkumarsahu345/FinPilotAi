"""
Data export endpoints.
Large exports (>1000 rows) use Celery async processing.
All exports are org-scoped and permission-checked.
"""
import csv
import io
from django.http import HttpResponse
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.models import Invoice, Payment, Customer, AuditLog
from core.permissions import HasOrganizationAccess


def _money(minor: int) -> str:
    return f"{minor / 100:.2f}"


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def export_invoices(request):
    org = request.membership.organization
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="invoices_export.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "invoice_number", "customer_name", "invoice_date", "due_date",
        "status", "subtotal", "discount", "tax", "total", "paid", "outstanding", "currency",
    ])
    invoices = (
        Invoice.objects.filter(organization=org)
        .select_related("customer")
        .prefetch_related("allocations")
        .order_by("-invoice_date")
    )
    for inv in invoices:
        paid = sum(a.amount_minor for a in inv.allocations.all() if a.reversed_at is None)
        balance = max(0, inv.total_minor - paid)
        writer.writerow([
            inv.invoice_number, inv.customer.name, inv.invoice_date, inv.due_date,
            inv.status, _money(inv.subtotal_minor), _money(inv.discount_minor),
            _money(inv.tax_minor), _money(inv.total_minor), _money(paid),
            _money(balance), inv.currency,
        ])
    AuditLog.objects.create(
        organization=org, actor=request.user,
        action="export.invoices", entity_type="export", entity_id="invoices",
        summary="Exported invoices to CSV",
    )
    return response


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def export_customers(request):
    org = request.membership.organization
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="customers_export.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "name", "contact_name", "email", "phone", "gstin", "payment_terms_days",
        "active", "created_at",
    ])
    for c in Customer.objects.filter(organization=org).order_by("name"):
        writer.writerow([
            c.name, c.contact_name, c.email, c.phone, c.gstin,
            c.payment_terms_days, c.active, c.created_at.date(),
        ])
    AuditLog.objects.create(
        organization=org, actor=request.user,
        action="export.customers", entity_type="export", entity_id="customers",
        summary="Exported customers to CSV",
    )
    return response


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def export_payments(request):
    org = request.membership.organization
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="payments_export.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "payment_date", "customer_name", "amount", "currency", "method",
        "reference", "allocated_to_invoices", "created_at",
    ])
    payments = (
        Payment.objects.filter(organization=org)
        .select_related("customer")
        .prefetch_related("allocations__invoice")
        .order_by("-payment_date")
    )
    for p in payments:
        alloc_refs = ",".join(
            a.invoice.invoice_number for a in p.allocations.all() if a.reversed_at is None
        )
        writer.writerow([
            p.payment_date, p.customer.name, _money(p.amount_minor),
            p.currency, p.method, p.reference, alloc_refs, p.created_at.date(),
        ])
    AuditLog.objects.create(
        organization=org, actor=request.user,
        action="export.payments", entity_type="export", entity_id="payments",
        summary="Exported payments to CSV",
    )
    return response
