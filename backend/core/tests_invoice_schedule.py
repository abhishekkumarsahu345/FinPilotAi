"""
Tests for invoice reminder schedule selection (Step 3 of reminder feature).
"""
import pytest
from datetime import date, timedelta
from django.contrib.auth import get_user_model

from core.models import Organization, Membership, Customer, Invoice
from reminders.models import ReminderSchedule, ReminderStep, ReminderTemplate, ReminderJob
from reminders.schedule_tasks import get_schedule_for_invoice

User = get_user_model()


def _authed_client(user, org):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return client


@pytest.fixture
def org():
    return Organization.objects.create(name="Test Org", timezone="Asia/Kolkata", business_email="finance@test.in")


@pytest.fixture
def org2():
    return Organization.objects.create(name="Other Org", timezone="Asia/Kolkata")


@pytest.fixture
def owner(org):
    u = User.objects.create_user(username="owner_sch", email="owner_sch@test.in", password="pass")
    Membership.objects.create(organization=org, user=u, role=Membership.Role.OWNER)
    return u


@pytest.fixture
def customer(org):
    return Customer.objects.create(organization=org, name="ACME Corp", email="acme@example.com", payment_terms_days=30)


@pytest.fixture
def template(org, owner):
    return ReminderTemplate.objects.create(organization=org, name="Test Template", channel="email", subject="Test", body="Test body", active=True, created_by=owner)


@pytest.fixture
def default_schedule(org, owner, template):
    sched = ReminderSchedule.objects.create(organization=org, name="Default Schedule", enabled=True, is_default=True, created_by=owner)
    ReminderStep.objects.create(schedule=sched, step_number=1, offset_from_due=0, template=template)
    return sched


@pytest.fixture
def custom_schedule(org, owner, template):
    sched = ReminderSchedule.objects.create(organization=org, name="Aggressive Schedule", enabled=True, is_default=False, created_by=owner)
    ReminderStep.objects.create(schedule=sched, step_number=1, offset_from_due=-1, template=template)
    return sched


@pytest.fixture
def archived_schedule(org, owner):
    return ReminderSchedule.objects.create(organization=org, name="Archived Schedule", enabled=True, is_default=False, archived=True, created_by=owner)


@pytest.mark.django_db
def test_migration_adds_fields(org, owner, customer):
    invoice = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-M-001", invoice_date=date.today(), due_date=date.today() + timedelta(days=30), currency="INR", subtotal_minor=100000, discount_minor=0, tax_minor=0, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner)
    assert hasattr(invoice, "reminder_schedule")
    assert hasattr(invoice, "no_reminders")
    assert invoice.reminder_schedule is None
    assert invoice.no_reminders is False


@pytest.mark.django_db
def test_get_schedule_explicit(org, owner, customer, custom_schedule):
    invoice = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-S-002", invoice_date=date.today(), due_date=date.today() + timedelta(days=30), currency="INR", subtotal_minor=100000, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner, reminder_schedule=custom_schedule)
    schedule = get_schedule_for_invoice(invoice)
    assert schedule is not None
    assert schedule.id == custom_schedule.id


@pytest.mark.django_db
def test_get_schedule_default_fallback(org, owner, customer, default_schedule):
    invoice = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-S-003", invoice_date=date.today(), due_date=date.today() + timedelta(days=30), currency="INR", subtotal_minor=100000, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner, reminder_schedule=None)
    schedule = get_schedule_for_invoice(invoice)
    assert schedule is not None
    assert schedule.id == default_schedule.id
    assert schedule.is_default is True


@pytest.mark.django_db
def test_get_schedule_archived_fallback(org, owner, customer, archived_schedule, default_schedule):
    invoice = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-S-004", invoice_date=date.today(), due_date=date.today() + timedelta(days=30), currency="INR", subtotal_minor=100000, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner, reminder_schedule=archived_schedule)
    schedule = get_schedule_for_invoice(invoice)
    assert schedule is not None
    assert schedule.id == default_schedule.id


@pytest.mark.django_db
def test_get_schedule_no_reminders(org, owner, customer, default_schedule):
    invoice = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-S-005", invoice_date=date.today(), due_date=date.today() + timedelta(days=30), currency="INR", subtotal_minor=100000, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner, no_reminders=True)
    assert get_schedule_for_invoice(invoice) is None


@pytest.mark.django_db
def test_get_schedule_no_default_exists(org, owner, customer):
    invoice = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-S-006", invoice_date=date.today(), due_date=date.today() + timedelta(days=30), currency="INR", subtotal_minor=100000, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner, reminder_schedule=None)
    assert get_schedule_for_invoice(invoice) is None


@pytest.mark.django_db
def test_create_invoice_with_schedule(org, owner, customer, custom_schedule):
    client = _authed_client(owner, org)
    response = client.post("/api/v1/invoices/", {"customer": str(customer.id), "invoice_number": "INV-API-001", "invoice_date": str(date.today()), "due_date": str(date.today() + timedelta(days=30)), "currency": "INR", "subtotal_minor": 100000, "discount_minor": 0, "tax_minor": 0, "status": "issued", "reminder_schedule": str(custom_schedule.id)}, format="json")
    assert response.status_code == 201
    data = response.json()
    assert data["reminder_schedule"] == str(custom_schedule.id)
    assert data["reminder_schedule_name"] == "Aggressive Schedule"
    invoice = Invoice.objects.get(id=data["id"])
    assert invoice.reminder_schedule_id == custom_schedule.id


@pytest.mark.django_db
def test_create_invoice_no_schedule(org, owner, customer, default_schedule):
    client = _authed_client(owner, org)
    response = client.post("/api/v1/invoices/", {"customer": str(customer.id), "invoice_number": "INV-API-002", "invoice_date": str(date.today()), "due_date": str(date.today() + timedelta(days=30)), "currency": "INR", "subtotal_minor": 100000, "status": "issued"}, format="json")
    assert response.status_code == 201
    data = response.json()
    assert data["reminder_schedule"] is None
    assert data["reminder_schedule_name"] == "Default schedule"
    assert Invoice.objects.get(id=data["id"]).reminder_schedule is None


@pytest.mark.django_db
def test_create_invoice_no_reminders(org, owner, customer):
    client = _authed_client(owner, org)
    response = client.post("/api/v1/invoices/", {"customer": str(customer.id), "invoice_number": "INV-API-003", "invoice_date": str(date.today()), "due_date": str(date.today() + timedelta(days=30)), "currency": "INR", "subtotal_minor": 100000, "status": "issued", "no_reminders": True}, format="json")
    assert response.status_code == 201
    data = response.json()
    assert data["no_reminders"] is True
    assert data["reminder_schedule_name"] == "No reminders"
    assert Invoice.objects.get(id=data["id"]).no_reminders is True


@pytest.mark.django_db
def test_update_invoice_schedule_reschedules(org, owner, customer, default_schedule, custom_schedule):
    client = _authed_client(owner, org)
    invoice = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-UPD-001", invoice_date=date.today(), due_date=date.today() + timedelta(days=30), currency="INR", subtotal_minor=100000, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner, reminder_schedule=default_schedule)
    job_old = ReminderJob.objects.create(organization=org, schedule=default_schedule, step=default_schedule.steps.first(), invoice=invoice, customer=customer, scheduled_date=date.today() + timedelta(days=30), balance_at_scheduling_minor=100000, snapshot_total_minor=100000, snapshot_outstanding_minor=100000, snapshot_due_date=invoice.due_date, snapshot_days_overdue=0, idempotency_key=f"upd-test:{default_schedule.id}:{invoice.id}", status=ReminderJob.Status.PROPOSED)
    response = client.patch(f"/api/v1/invoices/{invoice.id}/", {"reminder_schedule": str(custom_schedule.id)}, format="json")
    assert response.status_code == 200
    assert response.json()["reminder_schedule"] == str(custom_schedule.id)
    job_old.refresh_from_db()
    assert job_old.status == ReminderJob.Status.REJECTED
    assert "Schedule changed" in job_old.block_reason


@pytest.mark.django_db
def test_scheduler_respects_invoice_schedule(org, owner, customer, default_schedule, custom_schedule):
    from reminders.schedule_tasks import schedule_step_reminders
    inv1 = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-JOB-001", invoice_date=date.today() - timedelta(days=30), due_date=date.today(), currency="INR", subtotal_minor=100000, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner, reminder_schedule=None)
    inv2 = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-JOB-002", invoice_date=date.today() - timedelta(days=30), due_date=date.today() + timedelta(days=1), currency="INR", subtotal_minor=100000, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner, reminder_schedule=custom_schedule)
    schedule_step_reminders()
    jobs_inv1 = ReminderJob.objects.filter(invoice=inv1)
    assert jobs_inv1.count() == 1
    assert jobs_inv1.first().schedule.id == default_schedule.id
    jobs_inv2 = ReminderJob.objects.filter(invoice=inv2)
    assert jobs_inv2.count() == 1
    assert jobs_inv2.first().schedule.id == custom_schedule.id


@pytest.mark.django_db
def test_cross_org_schedule_rejected(org, org2, owner, customer):
    owner2 = User.objects.create_user(username="owner2_sch", email="owner2_sch@test.in", password="pass")
    Membership.objects.create(organization=org2, user=owner2, role=Membership.Role.OWNER)
    ReminderTemplate.objects.create(organization=org2, name="Org2 Template", channel="email", subject="Test", body="Test", active=True, created_by=owner2)
    sched_org2 = ReminderSchedule.objects.create(organization=org2, name="Org2 Schedule", enabled=True, created_by=owner2)
    client = _authed_client(owner, org)
    response = client.post("/api/v1/invoices/", {"customer": str(customer.id), "invoice_number": "INV-XO-001", "invoice_date": str(date.today()), "due_date": str(date.today() + timedelta(days=30)), "currency": "INR", "subtotal_minor": 100000, "status": "issued", "reminder_schedule": str(sched_org2.id)}, format="json")
    assert response.status_code == 400
    assert "reminder_schedule" in response.json()


@pytest.mark.django_db
def test_archived_schedule_on_invoice_uses_default(org, owner, customer, archived_schedule, default_schedule):
    invoice = Invoice.objects.create(organization=org, customer=customer, invoice_number="INV-ARC-001", invoice_date=date.today(), due_date=date.today(), currency="INR", subtotal_minor=100000, total_minor=100000, status=Invoice.Status.ISSUED, created_by=owner, reminder_schedule=archived_schedule)
    schedule = get_schedule_for_invoice(invoice)
    assert schedule is not None
    assert schedule.id == default_schedule.id
    assert schedule.is_default is True