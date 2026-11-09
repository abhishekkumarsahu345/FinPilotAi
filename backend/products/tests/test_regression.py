"""Regression tests: GST-inclusive invoice totals flow unchanged into
outstanding balance, aging, and dashboard; and old-style invoices
(explicit totals, no items) still behave exactly as before.
"""
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import (
    Organization, Membership, Customer, Invoice, Payment, PaymentAllocation,
)

User = get_user_model()


class RegressionTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="reg@example.com", email="reg@example.com", password="Testpass1!"
        )
        self.org = Organization.objects.create(name="Reg Org", default_currency="INR", state="07")
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        self.client.force_authenticate(user=self.user)
        self.cust = Customer.objects.create(organization=self.org, name="Reg Customer", state="07")
        self.headers = {"HTTP_X_ORGANIZATION_ID": str(self.org.id)}

    def _create_gst_invoice(self, number="REG-G1", due=None):
        due = due or (date.today() + timedelta(days=30))
        payload = {
            "customer": str(self.cust.id), "invoice_number": number,
            "invoice_date": str(date.today()), "due_date": str(due),
            "currency": "INR", "discount_minor": 0, "status": "issued",
            "items": [{
                "description": "Service", "quantity": 1, "unit_price_minor": 100_000,
                "discount_minor": 0, "gst_rate_bps": 1800, "gst_rate_name": "18% GST",
                "hsn_sac": "998313",
            }],
        }
        r = self.client.post("/api/v1/invoices/", payload, format="json", **self.headers)
        assert r.status_code == 201, r.content
        return r.json()

    # ── GST invoice balance after partial payment ─────────────────────────
    def test_gst_invoice_balance_after_partial_payment(self):
        inv = self._create_gst_invoice()
        # total = 118000 ; pay 50000
        p = self.client.post("/api/v1/payments/", {
            "customer": str(self.cust.id), "payment_date": str(date.today()),
            "amount_minor": 50_000, "currency": "INR", "method": "upi",
            "allocations_input": [{"invoice": inv["id"], "amount_minor": 50_000}],
        }, format="json", **self.headers)
        assert p.status_code == 201, p.content
        got = self.client.get(f"/api/v1/invoices/{inv['id']}/", **self.headers).json()
        assert got["total_minor"] == 118_000
        assert got["paid_minor"] == 50_000
        assert got["balance_minor"] == 68_000
        assert got["display_status"] == "partially_paid"

    # ── GST invoice fully paid ────────────────────────────────────────────
    def test_gst_invoice_fully_paid(self):
        inv = self._create_gst_invoice()
        self.client.post("/api/v1/payments/", {
            "customer": str(self.cust.id), "payment_date": str(date.today()),
            "amount_minor": 118_000, "currency": "INR", "method": "upi",
            "allocations_input": [{"invoice": inv["id"], "amount_minor": 118_000}],
        }, format="json", **self.headers)
        got = self.client.get(f"/api/v1/invoices/{inv['id']}/", **self.headers).json()
        assert got["balance_minor"] == 0
        assert got["display_status"] == "paid"

    # ── Aging reflects GST-inclusive balance ──────────────────────────────
    def test_aging_includes_gst_invoice(self):
        # Overdue: due 10 days ago
        inv = self._create_gst_invoice(
            number="REG-OV", due=date.today() - timedelta(days=10)
        )
        a = self.client.get("/api/v1/reports/aging/", **self.headers).json()
        # invoice total 118000, balance 118000, 10 days overdue -> days_1_30
        bucket = a["buckets"]["days_1_30"]
        assert any(r["invoice_number"] == "REG-OV" for r in bucket)
        match = [r for r in bucket if r["invoice_number"] == "REG-OV"][0]
        assert match["balance_minor"] == 118_000
        assert match["days_overdue"] == 10
        assert a["bucket_totals"]["days_1_30"] >= 118_000

    # ── Dashboard outstanding includes GST-inclusive total ────────────────
    def test_dashboard_outstanding_includes_gst_invoice(self):
        inv = self._create_gst_invoice(number="REG-DB")
        d = self.client.get("/api/v1/dashboard/", **self.headers).json()
        # issued, not paid -> outstanding includes 118000
        assert d["outstanding_minor"] >= 118_000
        # partially pay and check outstanding drops
        self.client.post("/api/v1/payments/", {
            "customer": str(self.cust.id), "payment_date": str(date.today()),
            "amount_minor": 50_000, "currency": "INR", "method": "upi",
            "allocations_input": [{"invoice": inv["id"], "amount_minor": 50_000}],
        }, format="json", **self.headers)
        d2 = self.client.get("/api/v1/dashboard/", **self.headers).json()
        assert d2["outstanding_minor"] == d["outstanding_minor"] - 50_000

    # ── Old-style invoice (explicit totals, no items) still works ─────────
    def test_old_style_invoice_without_items(self):
        r = self.client.post("/api/v1/invoices/", {
            "customer": str(self.cust.id), "invoice_number": "REG-OLD",
            "invoice_date": str(date.today()),
            "due_date": str(date.today() + timedelta(days=30)),
            "currency": "INR", "subtotal_minor": 50_000, "discount_minor": 0,
            "tax_minor": 9_000, "status": "issued",
        }, format="json", **self.headers)
        assert r.status_code == 201, r.content
        inv = r.json()
        # subtotal - discount + tax = 50000 + 9000 = 59000
        assert inv["total_minor"] == 59_000
        assert inv["balance_minor"] == 59_000
        assert inv["gst_summary"]["has_gst"] is False

    # ── Existing arithmetic contract still holds for explicit totals ─────
    def test_explicit_total_formula_unchanged(self):
        inv = Invoice.objects.create(
            organization=self.org, customer=self.cust, invoice_number="REG-F",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            currency="INR", subtotal_minor=100_000, discount_minor=5_000,
            tax_minor=17_100, total_minor=112_100, status=Invoice.Status.ISSUED,
            created_by=self.user,
        )
        assert inv.total_minor == inv.subtotal_minor - inv.discount_minor + inv.tax_minor
