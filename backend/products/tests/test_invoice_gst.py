"""End-to-end GST tests through the invoice API: calculation, snapshot
immutability, and org isolation. Uses DRF APIClient + force_authenticate,
matching the ai_assistant test style.
"""
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import (
    Organization, Membership, Customer, Invoice, InvoiceItem,
    AuditLog,
)
from products.models import GSTRate, Product

User = get_user_model()


class InvoiceGstTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="gst@example.com", email="gst@example.com", password="Testpass1!"
        )
        self.org = Organization.objects.create(name="GST Org", default_currency="INR", state="07")
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        self.client.force_authenticate(user=self.user)

        self.rate18 = GSTRate.objects.create(organization=self.org, name="18% GST", rate_bps=1800)
        self.rate5 = GSTRate.objects.create(organization=self.org, name="5% GST", rate_bps=500)

        # Intra-state customer (same state as org -> CGST+SGST)
        self.cust_intra = Customer.objects.create(
            organization=self.org, name="Intra Customer", state="07"
        )
        # Inter-state customer (different state -> IGST)
        self.cust_inter = Customer.objects.create(
            organization=self.org, name="Inter Customer", state="29"
        )
        self.url = "/api/v1/invoices/"

    def _create(self, payload):
        resp = self.client.post(
            self.url, payload, format="json", HTTP_X_ORGANIZATION_ID=str(self.org.id)
        )
        assert resp.status_code == 201, resp.content
        return resp.json()

    def _line(self, unit=100_000, rate_bps=1800, qty=1, disc=0, desc="Widget", hsn="998313"):
        return {
            "description": desc, "quantity": qty, "unit_price_minor": unit,
            "discount_minor": disc, "gst_rate_bps": rate_bps,
            "gst_rate_name": f"{rate_bps // 100}% GST" if rate_bps else "No GST",
            "hsn_sac": hsn,
        }

    # ── Intra-state: CGST + SGST ──────────────────────────────────────────
    def test_intra_state_cgst_sgst(self):
        inv = self._create({
            "customer": str(self.cust_intra.id), "invoice_number": "INV-I1",
            "invoice_date": "2026-11-06", "due_date": "2026-12-06",
            "currency": "INR", "discount_minor": 0, "status": "issued",
            "items": [self._line(unit=100_000, rate_bps=1800)],
        })
        # subtotal = 100000, tax = 18000, total = 118000
        assert inv["subtotal_minor"] == 100_000
        assert inv["tax_minor"] == 18_000
        assert inv["total_minor"] == 118_000
        item = inv["items"][0]
        assert item["gst_tax_minor"] == 18_000
        assert item["gst_cgst_minor"] == 9_000
        assert item["gst_sgst_minor"] == 9_000
        assert item["gst_igst_minor"] == 0
        assert inv["gst_summary"]["has_gst"] is True
        assert inv["gst_summary"]["place_of_supply"] == "intra_state"
        assert inv["gst_summary"]["totals"]["cgst_minor"] == 9_000
        assert inv["gst_summary"]["totals"]["sgst_minor"] == 9_000
        assert inv["gst_summary"]["totals"]["igst_minor"] == 0
        assert inv["gst_summary"]["totals"]["grand_total_minor"] == 118_000

    # ── Inter-state: IGST ─────────────────────────────────────────────────
    def test_inter_state_igst(self):
        inv = self._create({
            "customer": str(self.cust_inter.id), "invoice_number": "INV-I2",
            "invoice_date": "2026-11-06", "due_date": "2026-12-06",
            "currency": "INR", "discount_minor": 0, "status": "issued",
            "items": [self._line(unit=100_000, rate_bps=1800)],
        })
        assert inv["tax_minor"] == 18_000
        assert inv["total_minor"] == 118_000
        item = inv["items"][0]
        assert item["gst_cgst_minor"] == 0
        assert item["gst_sgst_minor"] == 0
        assert item["gst_igst_minor"] == 18_000
        assert inv["gst_summary"]["place_of_supply"] == "inter_state"
        assert inv["gst_summary"]["totals"]["igst_minor"] == 18_000

    # ── No GST: tax 0, summary hidden ─────────────────────────────────────
    def test_no_gst_line(self):
        inv = self._create({
            "customer": str(self.cust_intra.id), "invoice_number": "INV-I3",
            "invoice_date": "2026-11-06", "due_date": "2026-12-06",
            "currency": "INR", "discount_minor": 0, "status": "issued",
            "items": [self._line(unit=50_000, rate_bps=0)],
        })
        assert inv["subtotal_minor"] == 50_000
        assert inv["tax_minor"] == 0
        assert inv["total_minor"] == 50_000
        assert inv["items"][0]["gst_tax_minor"] == 0
        assert inv["gst_summary"]["has_gst"] is False
        assert inv["gst_summary"]["totals"]["tax_minor"] == 0

    # ── Line discount + invoice discount ─────────────────────────────────
    def test_discounts(self):
        inv = self._create({
            "customer": str(self.cust_intra.id), "invoice_number": "INV-I4",
            "invoice_date": "2026-11-06", "due_date": "2026-12-06",
            "currency": "INR", "discount_minor": 5_000, "status": "issued",
            "items": [self._line(unit=100_000, rate_bps=1800, disc=10_000)],
        })
        # line_total = 100000 - 10000 = 90000 ; tax = 18% of 90000 = 16200
        # total = subtotal(90000) - invoice_discount(5000) + tax(16200) = 101200
        assert inv["subtotal_minor"] == 90_000
        assert inv["tax_minor"] == 16_200
        assert inv["total_minor"] == 101_200
        assert inv["items"][0]["gst_tax_minor"] == 16_200

    # ── Rounding (half-up) ────────────────────────────────────────────────
    def test_rounding_half_up(self):
        inv = self._create({
            "customer": str(self.cust_intra.id), "invoice_number": "INV-I5",
            "invoice_date": "2026-11-06", "due_date": "2026-12-06",
            "currency": "INR", "discount_minor": 0, "status": "issued",
            "items": [self._line(unit=33_333, rate_bps=1800)],
        })
        # 33333 * 18% = 5999.94 -> 6000 (half up); cgst=sgst=3000
        assert inv["items"][0]["gst_tax_minor"] == 6_000
        assert inv["items"][0]["gst_cgst_minor"] == 3_000
        assert inv["items"][0]["gst_sgst_minor"] == 3_000
        assert inv["items"][0]["gst_cgst_minor"] + inv["items"][0]["gst_sgst_minor"] == inv["items"][0]["gst_tax_minor"]

    # ── Mixed-rate invoice ────────────────────────────────────────────────
    def test_mixed_rates_intra(self):
        inv = self._create({
            "customer": str(self.cust_intra.id), "invoice_number": "INV-I6",
            "invoice_date": "2026-11-06", "due_date": "2026-12-06",
            "currency": "INR", "discount_minor": 0, "status": "issued",
            "items": [
                self._line(unit=100_000, rate_bps=1800, desc="A"),
                self._line(unit=50_000, rate_bps=500, desc="B"),
            ],
        })
        # subtotal=150000 ; tax=18000+2500=20500 ; total=170500
        assert inv["subtotal_minor"] == 150_000
        assert inv["tax_minor"] == 20_500
        assert inv["total_minor"] == 170_500
        # cgst total = 9000 + 1250 = 10250 ; sgst = 10250
        assert inv["gst_summary"]["totals"]["cgst_minor"] == 10_250
        assert inv["gst_summary"]["totals"]["sgst_minor"] == 10_250
        assert inv["gst_summary"]["totals"]["tax_minor"] == 20_500
        # two rate groups
        rates = {r["rate_bps"]: r for r in inv["gst_summary"]["rates"]}
        assert set(rates.keys()) == {1800, 500}
        assert rates[1800]["taxable_minor"] == 100_000
        assert rates[500]["taxable_minor"] == 50_000

    # ── Snapshot immutability: editing a GSTRate never changes old invoices ─
    def test_snapshot_immutability(self):
        inv = self._create({
            "customer": str(self.cust_intra.id), "invoice_number": "INV-S1",
            "invoice_date": "2026-11-06", "due_date": "2026-12-06",
            "currency": "INR", "discount_minor": 0, "status": "issued",
            "items": [self._line(unit=100_000, rate_bps=1800)],
        })
        assert inv["total_minor"] == 118_000

        # Edit the rate from 18% to 28%
        r = self.client.patch(
            f"/api/v1/gst-rates/{self.rate18.id}/",
            {"rate_bps": 2800, "name": "28% GST"},
            format="json", HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        assert r.status_code == 200, r.content

        # Reload the invoice — its line must still reflect 18% and original totals
        got = self.client.get(
            f"/api/v1/invoices/{inv['id']}/",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        ).json()
        assert got["items"][0]["gst_rate_bps"] == 1800
        assert got["items"][0]["gst_tax_minor"] == 18_000
        assert got["subtotal_minor"] == 100_000
        assert got["tax_minor"] == 18_000
        assert got["total_minor"] == 118_000

    # ── Product auto-fill: line referencing a product keeps snapshot ──────
    def test_product_link_and_snapshot(self):
        product = Product.objects.create(
            organization=self.org, name="Gadget", price_minor=20_000,
            unit="Nos", hsn_sac="8517", default_gst_rate=self.rate18,
        )
        inv = self._create({
            "customer": str(self.cust_intra.id), "invoice_number": "INV-P1",
            "invoice_date": "2026-11-06", "due_date": "2026-12-06",
            "currency": "INR", "discount_minor": 0, "status": "issued",
            "items": [{
                "product": str(product.id), "description": "Gadget",
                "quantity": 2, "unit_price_minor": 20_000, "discount_minor": 0,
                "gst_rate_bps": 1800, "gst_rate_name": "18% GST", "hsn_sac": "8517",
            }],
        })
        # 2 * 20000 = 40000 ; tax 18% = 7200 ; total = 47200
        assert inv["subtotal_minor"] == 40_000
        assert inv["tax_minor"] == 7_200
        assert inv["total_minor"] == 47_200
        # Deactivate the product -> invoice line unaffected (snapshot)
        self.client.post(
            f"/api/v1/products/{product.id}/deactivate/",
            HTTP_X_ORGANIZATION_ID=str(self.org.id),
        )
        got = self.client.get(
            f"/api/v1/invoices/{inv['id']}/", HTTP_X_ORGANIZATION_ID=str(self.org.id)
        ).json()
        assert got["items"][0]["gst_rate_bps"] == 1800
        assert got["total_minor"] == 47_200


class GstOrgIsolationTest(TestCase):
    def test_products_and_rates_scoped_to_org(self):
        client = APIClient()
        u1 = User.objects.create_user(username="a@x.com", email="a@x.com", password="p")
        u2 = User.objects.create_user(username="b@x.com", email="b@x.com", password="p")
        org1 = Organization.objects.create(name="Org1", default_currency="INR")
        org2 = Organization.objects.create(name="Org2", default_currency="INR")
        Membership.objects.create(organization=org1, user=u1, role=Membership.Role.OWNER)
        Membership.objects.create(organization=org2, user=u2, role=Membership.Role.OWNER)

        r1 = GSTRate.objects.create(organization=org1, name="18% GST", rate_bps=1800)
        p1 = Product.objects.create(organization=org1, name="Widget", price_minor=1000)

        client.force_authenticate(user=u1)
        # Org1 sees its product; Org2's (nonexistent for org1) -> 404
        res = client.get("/api/v1/products/", HTTP_X_ORGANIZATION_ID=str(org1.id))
        assert res.status_code == 200
        ids = [p["id"] for p in res.json()["results"]]
        assert str(p1.id) in ids

        client.force_authenticate(user=u2)
        res2 = client.get("/api/v1/products/", HTTP_X_ORGANIZATION_ID=str(org2.id))
        assert res2.status_code == 200
        assert res2.json()["results"] == []
        # Org2 cannot access org1's product by id
        res3 = client.get(f"/api/v1/products/{p1.id}/", HTTP_X_ORGANIZATION_ID=str(org2.id))
        assert res3.status_code == 404
        # Org2 cannot access org1's gst rate by id
        res4 = client.get(f"/api/v1/gst-rates/{r1.id}/", HTTP_X_ORGANIZATION_ID=str(org2.id))
        assert res4.status_code == 404


class GstAuditTest(TestCase):
    def test_product_and_rate_actions_audited(self):
        client = APIClient()
        user = User.objects.create_user(username="a@x.com", email="a@x.com", password="p")
        org = Organization.objects.create(name="Org", default_currency="INR")
        Membership.objects.create(organization=org, user=user, role=Membership.Role.OWNER)
        client.force_authenticate(user=user)

        # Create rate
        r = client.post("/api/v1/gst-rates/", {"name": "12% GST", "rate_bps": 1200},
                        format="json", HTTP_X_ORGANIZATION_ID=str(org.id))
        assert r.status_code == 201
        rid = r.json()["id"]
        # Create product
        p = client.post("/api/v1/products/", {"name": "Bolt", "price_minor": 500},
                        format="json", HTTP_X_ORGANIZATION_ID=str(org.id))
        assert p.status_code == 201
        pid = p.json()["id"]
        # Update product
        client.patch(f"/api/v1/products/{pid}/", {"price_minor": 600},
                     format="json", HTTP_X_ORGANIZATION_ID=str(org.id))
        # Deactivate product
        client.post(f"/api/v1/products/{pid}/deactivate/",
                    HTTP_X_ORGANIZATION_ID=str(org.id))
        # Deactivate rate
        client.post(f"/api/v1/gst-rates/{rid}/deactivate/",
                    HTTP_X_ORGANIZATION_ID=str(org.id))

        actions = set(AuditLog.objects.filter(organization=org).values_list("action", flat=True))
        for a in ["gst_rate.created", "product.created", "product.updated",
                  "product.deactivated", "gst_rate.deactivated"]:
            assert a in actions, f"missing audit action {a}; got {actions}"
