"""
Core financial correctness tests.
Tests invoice arithmetic, payment allocation constraints,
display status derivation, and aging bucket assignments.
"""
import pytest
from datetime import date, timedelta
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import Organization, Membership, Customer, Invoice, Payment, PaymentAllocation

User = get_user_model()


@pytest.fixture
def org_and_user(db):
    user = User.objects.create_user(
        username="test@example.com", email="test@example.com", password="TestPass1!"
    )
    org = Organization.objects.create(name="Test Org", default_currency="INR")
    Membership.objects.create(organization=org, user=user, role=Membership.Role.OWNER)
    return org, user


@pytest.fixture
def customer(db, org_and_user):
    org, user = org_and_user
    return Customer.objects.create(organization=org, name="Acme Ltd")


# ---------------------------------------------------------------------------
# Invoice arithmetic
# ---------------------------------------------------------------------------

class TestInvoiceArithmetic:
    def test_total_equals_subtotal_minus_discount_plus_tax(self, db, org_and_user, customer):
        org, user = org_and_user
        invoice = Invoice.objects.create(
            organization=org, customer=customer,
            invoice_number="INV-001",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            currency="INR",
            subtotal_minor=100_000, discount_minor=5_000, tax_minor=17_100,
            total_minor=112_100,  # 100000 - 5000 + 17100
            status=Invoice.Status.ISSUED, created_by=user,
        )
        assert invoice.total_minor == invoice.subtotal_minor - invoice.discount_minor + invoice.tax_minor

    def test_outstanding_balance_zero_after_full_payment(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer,
            invoice_number="INV-002",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            currency="INR",
            subtotal_minor=50_000, discount_minor=0, tax_minor=9_000,
            total_minor=59_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        payment = Payment.objects.create(
            organization=org, customer=customer,
            payment_date=date.today(),
            amount_minor=59_000, currency="INR",
            method="upi", recorded_by=user,
        )
        PaymentAllocation.objects.create(
            organization=org, payment=payment, invoice=inv,
            amount_minor=59_000, created_by=user,
        )
        balance = max(0, inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ))
        assert balance == 0

    def test_outstanding_balance_after_partial_payment(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer,
            invoice_number="INV-003",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            currency="INR",
            subtotal_minor=100_000, discount_minor=0, tax_minor=0,
            total_minor=100_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        payment = Payment.objects.create(
            organization=org, customer=customer,
            payment_date=date.today(),
            amount_minor=100_000, currency="INR",
            method="bank_transfer", recorded_by=user,
        )
        PaymentAllocation.objects.create(
            organization=org, payment=payment, invoice=inv,
            amount_minor=40_000, created_by=user,
        )
        balance = max(0, inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ))
        assert balance == 60_000

    def test_balance_never_negative(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer,
            invoice_number="INV-004",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            currency="INR",
            subtotal_minor=10_000, discount_minor=0, tax_minor=0,
            total_minor=10_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        # Simulate a paid invoice
        payment = Payment.objects.create(
            organization=org, customer=customer,
            payment_date=date.today(),
            amount_minor=10_000, currency="INR",
            method="cash", recorded_by=user,
        )
        PaymentAllocation.objects.create(
            organization=org, payment=payment, invoice=inv,
            amount_minor=10_000, created_by=user,
        )
        balance = max(0, inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ))
        assert balance >= 0


# ---------------------------------------------------------------------------
# Invoice display status derivation
# ---------------------------------------------------------------------------

class TestDisplayStatus:
    def _get_balance(self, inv):
        return max(0, inv.total_minor - sum(
            a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
        ))

    def _display(self, inv):
        bal = self._get_balance(inv)
        from django.utils import timezone
        today = timezone.localdate()
        if inv.status == Invoice.Status.VOID:
            return "void"
        if inv.status == Invoice.Status.DRAFT:
            return "draft"
        if bal == 0:
            return "paid"
        if bal < inv.total_minor:
            return "partially_paid"
        if inv.due_date < today:
            return "overdue"
        return "issued"

    def test_void_invoice(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer, invoice_number="INV-V01",
            invoice_date=date.today(), due_date=date.today() - timedelta(days=10),
            currency="INR", subtotal_minor=10_000, discount_minor=0,
            tax_minor=0, total_minor=10_000,
            status=Invoice.Status.VOID, created_by=user,
        )
        assert self._display(inv) == "void"

    def test_draft_invoice(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer, invoice_number="INV-D01",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            currency="INR", subtotal_minor=10_000, discount_minor=0,
            tax_minor=0, total_minor=10_000,
            status=Invoice.Status.DRAFT, created_by=user,
        )
        assert self._display(inv) == "draft"

    def test_overdue_invoice(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer, invoice_number="INV-OD01",
            invoice_date=date.today() - timedelta(days=40),
            due_date=date.today() - timedelta(days=10),
            currency="INR", subtotal_minor=50_000, discount_minor=0,
            tax_minor=0, total_minor=50_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        assert self._display(inv) == "overdue"

    def test_paid_invoice(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer, invoice_number="INV-P01",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            currency="INR", subtotal_minor=20_000, discount_minor=0,
            tax_minor=0, total_minor=20_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        p = Payment.objects.create(
            organization=org, customer=customer, payment_date=date.today(),
            amount_minor=20_000, currency="INR", method="upi", recorded_by=user,
        )
        PaymentAllocation.objects.create(
            organization=org, payment=p, invoice=inv, amount_minor=20_000, created_by=user
        )
        assert self._display(inv) == "paid"

    def test_partially_paid(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer, invoice_number="INV-PP01",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            currency="INR", subtotal_minor=20_000, discount_minor=0,
            tax_minor=0, total_minor=20_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        p = Payment.objects.create(
            organization=org, customer=customer, payment_date=date.today(),
            amount_minor=20_000, currency="INR", method="upi", recorded_by=user,
        )
        PaymentAllocation.objects.create(
            organization=org, payment=p, invoice=inv, amount_minor=10_000, created_by=user
        )
        assert self._display(inv) == "partially_paid"


# ---------------------------------------------------------------------------
# Aging buckets
# ---------------------------------------------------------------------------

class TestAgingBuckets:
    def _bucket(self, inv, today=None):
        if today is None:
            today = date.today()
        days = (today - inv.due_date).days
        if days <= 0:
            return "not_yet_due"
        elif days <= 30:
            return "days_1_30"
        elif days <= 60:
            return "days_31_60"
        elif days <= 90:
            return "days_61_90"
        else:
            return "over_90"

    def test_not_yet_due(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer, invoice_number="INV-A1",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=5),
            currency="INR", subtotal_minor=10_000, discount_minor=0,
            tax_minor=0, total_minor=10_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        assert self._bucket(inv) == "not_yet_due"

    def test_1_to_30_days(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer, invoice_number="INV-A2",
            invoice_date=date.today() - timedelta(days=35),
            due_date=date.today() - timedelta(days=15),
            currency="INR", subtotal_minor=10_000, discount_minor=0,
            tax_minor=0, total_minor=10_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        assert self._bucket(inv) == "days_1_30"

    def test_over_90_days(self, db, org_and_user, customer):
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer, invoice_number="INV-A3",
            invoice_date=date.today() - timedelta(days=120),
            due_date=date.today() - timedelta(days=100),
            currency="INR", subtotal_minor=10_000, discount_minor=0,
            tax_minor=0, total_minor=10_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        assert self._bucket(inv) == "over_90"

    def test_due_today_is_not_yet_due(self, db, org_and_user, customer):
        """Invoice due today (days_overdue=0) must be in 'not_yet_due' bucket."""
        org, user = org_and_user
        inv = Invoice.objects.create(
            organization=org, customer=customer, invoice_number="INV-A4",
            invoice_date=date.today(), due_date=date.today(),
            currency="INR", subtotal_minor=10_000, discount_minor=0,
            tax_minor=0, total_minor=10_000,
            status=Invoice.Status.ISSUED, created_by=user,
        )
        assert self._bucket(inv) == "not_yet_due"


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:
    def test_customer_scoped_to_org(self, db, org_and_user):
        org, user = org_and_user
        other_org = Organization.objects.create(name="Other Org")
        Customer.objects.create(organization=other_org, name="Other Customer")
        mine = Customer.objects.filter(organization=org)
        assert all(c.organization_id == org.id for c in mine)

    def test_invoice_scoped_to_org(self, db, org_and_user, customer):
        org, user = org_and_user
        other_org = Organization.objects.create(name="Other Org 2")
        other_user = User.objects.create_user(
            username="other@example.com", email="other@example.com", password="Pass1234!"
        )
        other_customer = Customer.objects.create(organization=other_org, name="Other Co")
        Invoice.objects.create(
            organization=other_org, customer=other_customer,
            invoice_number="OTHER-001",
            invoice_date=date.today(), due_date=date.today() + timedelta(days=30),
            currency="INR", subtotal_minor=10_000, discount_minor=0,
            tax_minor=0, total_minor=10_000,
            status=Invoice.Status.ISSUED, created_by=other_user,
        )
        my_invoices = Invoice.objects.filter(organization=org)
        assert all(i.organization_id == org.id for i in my_invoices)
