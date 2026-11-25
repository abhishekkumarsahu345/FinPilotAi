"""
Tests that quantity display formatting flows through the reminder email rendering.

Run with:  pytest reminders/tests_email_quantity.py -v
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model

from core.models import Organization, Customer, Invoice, InvoiceItem
from reminders.email_rendering import build_invoice_context, render_html_email_body

User = get_user_model()


@pytest.fixture
def org(db):
    return Organization.objects.create(
        name="Test Org",
        timezone="Asia/Kolkata",
        business_email="finance@testorg.in",
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(username="email_qty_u1", email="email_qty_u1@test.com", password="pass")


@pytest.fixture
def customer(org):
    return Customer.objects.create(
        organization=org,
        name="Acme Corp",
        email="billing@acme.com",
        payment_terms_days=30,
    )


def _make_invoice(org, customer, user, qty_str, unit_price_minor=100000):
    """
    Create an invoice with a single line item.  The header totals are computed
    from the line so the DB check constraints are satisfied.
    """
    line_total = int(Decimal(qty_str) * unit_price_minor)
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        invoice_number="INV-QTY",
        invoice_date=date.today() - timedelta(days=25),
        due_date=date.today() + timedelta(days=5),
        currency="INR",
        subtotal_minor=line_total,
        discount_minor=0,
        tax_minor=0,
        total_minor=line_total,
        status=Invoice.Status.ISSUED,
        created_by=user,
    )
    InvoiceItem.objects.create(
        organization=org,
        invoice=inv,
        description="Test Item",
        quantity=Decimal(qty_str),
        unit_price_minor=unit_price_minor,
        discount_minor=0,
        line_total_minor=line_total,
        sort_order=0,
    )
    return inv


def _make_invoice_multi(org, customer, user, qty_strs, unit_price_minor=100000):
    """Create an invoice with multiple line items (one per qty_str)."""
    total = sum(int(Decimal(q) * unit_price_minor) for q in qty_strs)
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        invoice_number="INV-MULTI",
        invoice_date=date.today() - timedelta(days=25),
        due_date=date.today() + timedelta(days=5),
        currency="INR",
        subtotal_minor=total,
        discount_minor=0,
        tax_minor=0,
        total_minor=total,
        status=Invoice.Status.ISSUED,
        created_by=user,
    )
    for i, qty_str in enumerate(qty_strs):
        lt = int(Decimal(qty_str) * unit_price_minor)
        InvoiceItem.objects.create(
            organization=org,
            invoice=inv,
            description=f"Item {i}",
            quantity=Decimal(qty_str),
            unit_price_minor=unit_price_minor,
            discount_minor=0,
            line_total_minor=lt,
            sort_order=i,
        )
    return inv


@pytest.mark.django_db
class TestQuantityDisplayInEmail:
    def test_whole_quantity_shows_without_decimals(self, org, customer, user):
        inv = _make_invoice(org, customer, user, "5.0000")
        ctx = build_invoice_context(inv, customer, org)
        assert ctx["line_items"][0]["quantity"] == "5"

    def test_one_becomes_1_not_1_0000(self, org, customer, user):
        inv = _make_invoice(org, customer, user, "1.0000")
        ctx = build_invoice_context(inv, customer, org)
        assert ctx["line_items"][0]["quantity"] == "1"

    def test_fractional_quantities_drop_trailing_zeros(self, org, customer, user):
        inv = _make_invoice_multi(org, customer, user, ["2.5000", "0.7500", "1.2500"])
        ctx = build_invoice_context(inv, customer, org)
        quantities = [li["quantity"] for li in ctx["line_items"]]
        assert quantities == ["2.5", "0.75", "1.25"]

    def test_rendered_email_html_has_no_5_0000_style_quantities(self, org, customer, user):
        inv = _make_invoice_multi(org, customer, user, ["5.0000", "2.5000"])
        ctx = build_invoice_context(inv, customer, org)
        html = render_html_email_body(ctx, tone="friendly")
        # Qty cells should contain clean numbers, not raw "5.0000"
        assert ">5</td>" in html
        assert ">2.5</td>" in html
        assert "5.0000" not in html
        assert "2.5000" not in html

    def test_email_line_totals_unchanged_by_formatting(self, org, customer, user):
        """Display change must not alter money values: 5 × ₹1000.00 = ₹5,000.00."""
        inv = _make_invoice(org, customer, user, "5.0000")
        ctx = build_invoice_context(inv, customer, org)
        assert ctx["line_items"][0]["unit_price"] == "₹1,000.00"
        assert ctx["line_items"][0]["line_total"] == "₹5,000.00"
        assert ctx["total_amount"] == "₹5,000.00"
        assert ctx["outstanding_amount"] == "₹5,000.00"

    def test_email_qty_header_is_right_aligned(self, org, customer, user):
        """Qty column header should be right-aligned for clean numeric column layout."""
        inv = _make_invoice(org, customer, user, "5.0000")
        ctx = build_invoice_context(inv, customer, org)
        html = render_html_email_body(ctx, tone="friendly")
        assert "text-align: right;\">Qty</th>" in html

    def test_email_qty_cell_is_right_aligned(self, org, customer, user):
        """Qty data cells should be right-aligned."""
        inv = _make_invoice(org, customer, user, "5.0000")
        ctx = build_invoice_context(inv, customer, org)
        html = render_html_email_body(ctx, tone="friendly")
        # Qty data cells use text-align: right
        assert "text-align: right; white-space: nowrap;\">5</td>" in html
