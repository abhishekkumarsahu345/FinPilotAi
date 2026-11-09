"""Products & GST-rate API tests: CRUD, validation, soft-delete,
default-rate seeding, and org scoping. Style B (APIClient + force_authenticate).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Organization, Membership
from products.models import GSTRate, Product
from products.gst import create_default_gst_rates

User = get_user_model()


class DefaultsSeedingTest(TestCase):
    def test_create_default_gst_rates_seeds_five(self):
        org = Organization.objects.create(name="Seed Org", default_currency="INR")
        create_default_gst_rates(org)
        rates = list(GSTRate.objects.filter(organization=org).values_list("rate_bps", flat=True))
        self.assertEqual(sorted(rates), [0, 500, 1200, 1800, 2800])

    def test_create_default_gst_rates_idempotent(self):
        org = Organization.objects.create(name="Seed Org 2", default_currency="INR")
        create_default_gst_rates(org)
        create_default_gst_rates(org)  # second call must not duplicate
        self.assertEqual(GSTRate.objects.filter(organization=org).count(), 5)

    def test_register_seeds_default_rates(self):
        client = APIClient()
        resp = client.post("/api/v1/auth/register/", {
            "full_name": "Seed User", "email": "seed@example.com",
            "password": "SeedPass1!", "organization_name": "Seed Co",
        }, format="json")
        self.assertEqual(resp.status_code, 201, resp.content)
        org_id = resp.json()["organization_id"]
        # The new org should have the 5 default GST rates.
        rates = client.get("/api/v1/gst-rates/", HTTP_X_ORGANIZATION_ID=org_id).json()
        bps = sorted(r["rate_bps"] for r in rates["results"])
        self.assertEqual(bps, [0, 500, 1200, 1800, 2800])


class GSTRateApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="r@x.com", email="r@x.com", password="p")
        self.org = Organization.objects.create(name="R Org", default_currency="INR")
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        self.client.force_authenticate(user=self.user)
        self.h = {"HTTP_X_ORGANIZATION_ID": str(self.org.id)}

    def test_create_rate_with_preview(self):
        r = self.client.post("/api/v1/gst-rates/", {"name": "18% GST", "rate_bps": 1800},
                             format="json", **self.h)
        self.assertEqual(r.status_code, 201)
        body = r.json()
        self.assertEqual(body["rate_percent"], "18%")
        self.assertEqual(body["cgst_percent"], "9%")
        self.assertEqual(body["sgst_percent"], "9%")
        self.assertEqual(body["igst_percent"], "18%")
        self.assertEqual(body["preview"], "CGST 9% + SGST 9% | IGST 18%")
        self.assertTrue(body["in_use"] is False)

    def test_nil_rate_preview(self):
        r = self.client.post("/api/v1/gst-rates/", {"name": "Nil rate", "rate_bps": 0},
                             format="json", **self.h)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["preview"], "No GST")

    def test_duplicate_name_rejected(self):
        self.client.post("/api/v1/gst-rates/", {"name": "12% GST", "rate_bps": 1200},
                         format="json", **self.h)
        r = self.client.post("/api/v1/gst-rates/", {"name": "12% GST", "rate_bps": 1200},
                             format="json", **self.h)
        self.assertEqual(r.status_code, 400)

    def test_negative_rate_rejected(self):
        r = self.client.post("/api/v1/gst-rates/", {"name": "Bad", "rate_bps": -1},
                             format="json", **self.h)
        self.assertEqual(r.status_code, 400)

    def test_deactivate_and_activate(self):
        rid = self.client.post("/api/v1/gst-rates/", {"name": "5% GST", "rate_bps": 500},
                               format="json", **self.h).json()["id"]
        r = self.client.post(f"/api/v1/gst-rates/{rid}/deactivate/", **self.h)
        self.assertEqual(r.status_code, 200)
        self.assertFalse(r.json()["active"])
        r2 = self.client.post(f"/api/v1/gst-rates/{rid}/activate/", **self.h)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json()["active"])

    def test_hard_delete_not_allowed(self):
        rid = self.client.post("/api/v1/gst-rates/", {"name": "18% GST", "rate_bps": 1800},
                               format="json", **self.h).json()["id"]
        r = self.client.delete(f"/api/v1/gst-rates/{rid}/", **self.h)
        self.assertEqual(r.status_code, 405)  # delete not in http_method_names


class ProductApiTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username="p@x.com", email="p@x.com", password="p")
        self.org = Organization.objects.create(name="P Org", default_currency="INR")
        Membership.objects.create(organization=self.org, user=self.user, role=Membership.Role.OWNER)
        self.client.force_authenticate(user=self.user)
        self.h = {"HTTP_X_ORGANIZATION_ID": str(self.org.id)}
        self.rate = GSTRate.objects.create(organization=self.org, name="18% GST", rate_bps=1800)

    def test_create_product_with_default_gst(self):
        r = self.client.post("/api/v1/products/", {
            "name": "Widget", "price_minor": 1500, "unit": "Nos",
            "hsn_sac": "8517", "default_gst_rate": str(self.rate.id),
        }, format="json", **self.h)
        self.assertEqual(r.status_code, 201, r.content)
        body = r.json()
        self.assertEqual(body["default_gst_rate_bps"], 1800)
        self.assertEqual(body["default_gst_rate_preview"], "18%")

    def test_create_product_no_gst(self):
        r = self.client.post("/api/v1/products/", {"name": "Plain", "price_minor": 800},
                             format="json", **self.h)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["default_gst_rate_preview"], "No GST")

    def test_negative_price_rejected(self):
        r = self.client.post("/api/v1/products/", {"name": "Bad", "price_minor": 0},
                             format="json", **self.h)
        self.assertEqual(r.status_code, 400)

    def test_list_search_and_deactivate(self):
        self.client.post("/api/v1/products/", {"name": "Alpha", "price_minor": 100},
                         format="json", **self.h)
        self.client.post("/api/v1/products/", {"name": "Beta", "price_minor": 200},
                         format="json", **self.h)
        res = self.client.get("/api/v1/products/?search=alp", **self.h).json()
        self.assertEqual(len(res["results"]), 1)
        self.assertEqual(res["results"][0]["name"], "Alpha")
        pid = res["results"][0]["id"]
        d = self.client.post(f"/api/v1/products/{pid}/deactivate/", **self.h)
        self.assertFalse(d.json()["active"])
        # active filter excludes deactivated
        active = self.client.get("/api/v1/products/?active=true", **self.h).json()
        self.assertEqual(len(active["results"]), 1)
        self.assertEqual(active["results"][0]["name"], "Beta")

    def test_cross_org_rate_rejected(self):
        other = Organization.objects.create(name="Other", default_currency="INR")
        other_rate = GSTRate.objects.create(organization=other, name="18%", rate_bps=1800)
        r = self.client.post("/api/v1/products/", {
            "name": "X", "price_minor": 100, "default_gst_rate": str(other_rate.id),
        }, format="json", **self.h)
        self.assertEqual(r.status_code, 400)
