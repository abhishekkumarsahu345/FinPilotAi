"""
Comprehensive tests for the reminder (dunning) module.
"""
import pytest
from datetime import date, timedelta, datetime
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core import mail

from core.models import Organization, Membership, Customer, Invoice, Payment, PaymentAllocation
from reminders.models import ReminderTemplate, ReminderPolicy, ReminderJob
from reminders.tasks import schedule_reminders
from messaging.tasks import dispatch_reminder_job
from messaging.models import MessageLog

User = get_user_model()


@pytest.fixture
def org():
    return Organization.objects.create(
        name="Test Org",
        timezone="Asia/Kolkata",
        business_email="finance@testorg.in",
    )


@pytest.fixture
def owner_user():
    return User.objects.create_user(username="owner", email="owner@test.com", password="pass")


@pytest.fixture
def viewer_user():
    return User.objects.create_user(username="viewer", email="viewer@test.com", password="pass")


@pytest.fixture
def owner_membership(org, owner_user):
    return Membership.objects.create(
        organization=org,
        user=owner_user,
        role=Membership.Role.OWNER,
    )


@pytest.fixture
def viewer_membership(org, viewer_user):
    return Membership.objects.create(
        organization=org,
        user=viewer_user,
        role=Membership.Role.VIEWER,
    )


@pytest.fixture
def customer(org):
    return Customer.objects.create(
        organization=org,
        name="Acme Corp",
        email="billing@acme.com",
        payment_terms_days=30,
    )


@pytest.fixture
def customer_opted_out(org):
    return Customer.objects.create(
        organization=org,
        name="NoEmail Inc",
        opt_out=True,
        email="noemail@test.com",
    )


@pytest.fixture
def template(org, owner_user):
    return ReminderTemplate.objects.create(
        organization=org,
        name="Friendly Reminder",
        channel="email",
        subject="Invoice {{invoice_number}} due",
        body="Dear {{customer_name}}, your invoice {{invoice_number}} of {{outstanding_amount}} is due on {{due_date}}.",
        created_by=owner_user,
    )


@pytest.fixture
def policy(org, template, owner_user):
    return ReminderPolicy.objects.create(
        organization=org,
        name="7 days overdue",
        applicable_statuses=["issued"],
        trigger_offset_days=7,  # 7 days AFTER due date
        channel="email",
        template=template,
        send_hour=9,
        max_attempts=3,
        min_days_between_reminders=5,
        enabled=True,
        created_by=owner_user,
    )


@pytest.fixture
def invoice_due_7_days_ago(org, customer, owner_user):
    """Invoice due 7 days ago with outstanding balance."""
    inv = Invoice.objects.create(
        organization=org,
        customer=customer,
        invoice_number="INV-001",
        invoice_date=date.today() - timedelta(days=37),
        due_date=date.today() - timedelta(days=7),
        currency="INR",
        subtotal_minor=100000,  # ₹1,000
        discount_minor=0,
        tax_minor=18000,
        total_minor=118000,
        status=Invoice.Status.ISSUED,
        created_by=owner_user,
    )
    return inv


@pytest.fixture
def invoice_due_today(org, customer, owner_user):
    """Invoice due today."""
    return Invoice.objects.create(
        organization=org,
        customer=customer,
        invoice_number="INV-002",
        invoice_date=date.today() - timedelta(days=30),
        due_date=date.today(),
        currency="INR",
        subtotal_minor=50000,
        discount_minor=0,
        tax_minor=9000,
        total_minor=59000,
        status=Invoice.Status.ISSUED,
        created_by=owner_user,
    )


@pytest.mark.django_db
class TestReminderEligibility:
    """Test eligibility rules for reminder creation."""

    def test_eligible_invoice_creates_job(self, org, policy, invoice_due_7_days_ago):
        """An invoice due 7 days ago should trigger a reminder with offset=7."""
        result = schedule_reminders()
        assert result["scheduled"] == 1
        assert ReminderJob.objects.filter(invoice=invoice_due_7_days_ago).exists()

    def test_paid_invoice_no_reminder(self, org, policy, invoice_due_7_days_ago, owner_user):
        """Fully paid invoice should not get a reminder."""
        # Create payment that covers invoice
        payment = Payment.objects.create(
            organization=org,
            customer=invoice_due_7_days_ago.customer,
            payment_date=date.today(),
            amount_minor=118000,
            method=Payment.Method.BANK_TRANSFER,
            recorded_by=owner_user,
        )
        PaymentAllocation.objects.create(
            organization=org,
            payment=payment,
            invoice=invoice_due_7_days_ago,
            amount_minor=118000,
            created_by=owner_user,
        )
        
        result = schedule_reminders()
        assert result["scheduled"] == 0

    def test_opted_out_customer_no_reminder(self, org, policy, owner_user, customer_opted_out):
        """Customer who opted out should not receive reminders."""
        inv = Invoice.objects.create(
            organization=org,
            customer=customer_opted_out,
            invoice_number="INV-OPT",
            invoice_date=date.today() - timedelta(days=37),
            due_date=date.today() - timedelta(days=7),
            currency="INR",
            subtotal_minor=100000,
            discount_minor=0,
            tax_minor=18000,
            total_minor=118000,
            status=Invoice.Status.ISSUED,
            created_by=owner_user,
        )
        
        result = schedule_reminders()
        assert result["scheduled"] == 0

    def test_max_attempts_respected(self, org, policy, invoice_due_7_days_ago):
        """Should not create more jobs after max_attempts reached."""
        # Create 3 existing jobs (max_attempts = 3)
        for i in range(3):
            ReminderJob.objects.create(
                organization=org,
                policy=policy,
                invoice=invoice_due_7_days_ago,
                customer=invoice_due_7_days_ago.customer,
                scheduled_date=date.today() - timedelta(days=i * 5),
                balance_at_scheduling_minor=118000,
                idempotency_key=f"test-{i}",
                status=ReminderJob.Status.DISPATCHED,
            )
        
        result = schedule_reminders()
        assert result["scheduled"] == 0

    def test_min_days_between_reminders(self, org, policy, invoice_due_7_days_ago):
        """Should respect min_days_between_reminders (5 days in fixture)."""
        # Create a job dispatched 3 days ago (less than 5)
        ReminderJob.objects.create(
            organization=org,
            policy=policy,
            invoice=invoice_due_7_days_ago,
            customer=invoice_due_7_days_ago.customer,
            scheduled_date=date.today() - timedelta(days=3),
            balance_at_scheduling_minor=118000,
            idempotency_key="test-recent",
            status=ReminderJob.Status.DISPATCHED,
            dispatched_at=timezone.now() - timedelta(days=3),
        )
        
        result = schedule_reminders()
        assert result["scheduled"] == 0


@pytest.mark.django_db
class TestIdempotency:
    """Test duplicate prevention."""

    def test_duplicate_job_prevented(self, org, policy, invoice_due_7_days_ago):
        """Running scheduler twice should not create duplicate jobs."""
        result1 = schedule_reminders()
        result2 = schedule_reminders()
        
        assert result1["scheduled"] == 1
        assert result2["scheduled"] == 0
        assert ReminderJob.objects.filter(invoice=invoice_due_7_days_ago).count() == 1


@pytest.mark.django_db
class TestApprovalWorkflow:
    """Test approval-based sending."""

    def test_manual_mode_creates_proposed_job(self, org, policy, invoice_due_7_days_ago):
        """Manual mode should create PROPOSED job."""
        assert policy.approval_mode == ReminderPolicy.ApprovalMode.MANUAL
        schedule_reminders()
        
        job = ReminderJob.objects.get(invoice=invoice_due_7_days_ago)
        assert job.status == ReminderJob.Status.PROPOSED

    def test_automatic_mode_creates_scheduled_job(self, org, policy, invoice_due_7_days_ago, owner_user):
        """Automatic mode should create SCHEDULED job."""
        policy.approval_mode = ReminderPolicy.ApprovalMode.AUTOMATIC
        policy.auto_mode_confirmed_by = owner_user
        policy.save()
        
        schedule_reminders()
        
        job = ReminderJob.objects.get(invoice=invoice_due_7_days_ago)
        assert job.status == ReminderJob.Status.SCHEDULED


@pytest.mark.django_db
class TestDispatch:
    """Test message dispatch and sending."""

    def test_dispatch_sends_email(self, org, policy, invoice_due_7_days_ago, owner_user):
        """Dispatch should send email and create MessageLog."""
        job = ReminderJob.objects.create(
            organization=org,
            policy=policy,
            invoice=invoice_due_7_days_ago,
            customer=invoice_due_7_days_ago.customer,
            scheduled_date=date.today(),
            balance_at_scheduling_minor=118000,
            idempotency_key="test-dispatch",
            status=ReminderJob.Status.APPROVED,
        )
        
        # Clear mail outbox
        mail.outbox = []
        
        # Dispatch
        dispatch_reminder_job(str(job.id))
        
        # Refresh
        job.refresh_from_db()
        
        assert job.status == ReminderJob.Status.DISPATCHED
        assert job.dispatched_at is not None
        assert len(mail.outbox) == 1
        assert "INV-001" in mail.outbox[0].subject
        
        # Check MessageLog
        log = MessageLog.objects.get(reminder_job=job)
        assert log.status == MessageLog.Status.SENT
        assert log.channel == "email"
        assert log.recipient == invoice_due_7_days_ago.customer.email

    def test_dispatch_blocks_paid_invoice(self, org, policy, invoice_due_7_days_ago, owner_user):
        """Should block if invoice is paid after job creation but before dispatch."""
        job = ReminderJob.objects.create(
            organization=org,
            policy=policy,
            invoice=invoice_due_7_days_ago,
            customer=invoice_due_7_days_ago.customer,
            scheduled_date=date.today(),
            balance_at_scheduling_minor=118000,
            idempotency_key="test-block",
            status=ReminderJob.Status.APPROVED,
        )
        
        # Pay the invoice
        payment = Payment.objects.create(
            organization=org,
            customer=invoice_due_7_days_ago.customer,
            payment_date=date.today(),
            amount_minor=118000,
            method=Payment.Method.BANK_TRANSFER,
            recorded_by=owner_user,
        )
        PaymentAllocation.objects.create(
            organization=org,
            payment=payment,
            invoice=invoice_due_7_days_ago,
            amount_minor=118000,
            created_by=owner_user,
        )
        
        # Dispatch
        dispatch_reminder_job(str(job.id))
        
        job.refresh_from_db()
        assert job.status == ReminderJob.Status.BLOCKED
        assert "paid" in job.block_reason.lower()


@pytest.mark.django_db
class TestMultiTenancy:
    """Test organization isolation."""

    def test_jobs_isolated_by_org(self, org, policy, invoice_due_7_days_ago, owner_user):
        """Reminders should be strictly isolated by organization."""
        # Create second org with same invoice number
        org2 = Organization.objects.create(name="Org 2", timezone="Asia/Kolkata")
        customer2 = Customer.objects.create(
            organization=org2,
            name="Customer 2",
            email="cust2@test.com",
        )
        template2 = ReminderTemplate.objects.create(
            organization=org2,
            name="Template 2",
            channel="email",
            subject="Test",
            body="Test",
            created_by=owner_user,
        )
        policy2 = ReminderPolicy.objects.create(
            organization=org2,
            name="Policy 2",
            trigger_offset_days=7,
            channel="email",
            template=template2,
            enabled=True,
            created_by=owner_user,
        )
        Invoice.objects.create(
            organization=org2,
            customer=customer2,
            invoice_number="INV-001",  # Same number, different org
            invoice_date=date.today() - timedelta(days=37),
            due_date=date.today() - timedelta(days=7),
            currency="INR",
            subtotal_minor=100000,
            discount_minor=0,
            tax_minor=0,
            total_minor=100000,
            status=Invoice.Status.ISSUED,
            created_by=owner_user,
        )
        
        schedule_reminders()
        
        # Each org should have exactly 1 job
        assert ReminderJob.objects.filter(organization=org).count() == 1
        assert ReminderJob.objects.filter(organization=org2).count() == 1


@pytest.mark.django_db
class TestTemplateRendering:
    """Test template placeholder substitution."""

    def test_placeholders_rendered(self, org, policy, invoice_due_7_days_ago, owner_user):
        """All placeholders should be substituted correctly."""
        from reminders.serializers import render_template
        
        context = {
            "customer_name": "Acme Corp",
            "invoice_number": "INV-001",
            "invoice_date": "2024-01-01",
            "due_date": "2024-01-31",
            "outstanding_amount": "₹1,180.00",
            "payment_reference_instructions": "INV-001",
            "business_contact": "finance@testorg.in",
        }
        
        subject, body = render_template(
            policy.template.subject,
            policy.template.body,
            context
        )
        
        assert "INV-001" in subject
        assert "Acme Corp" in body
        assert "₹1,180.00" in body

    def test_unresolved_placeholder_raises(self):
        """Missing placeholder should raise ValueError."""
        from reminders.serializers import render_template
        
        with pytest.raises(ValueError, match="Unresolvable placeholder"):
            render_template("Hello {{missing}}", "", {})


@pytest.mark.django_db
class TestPermissions:
    """Test role-based access control."""

    def test_viewer_cannot_approve(self, org, viewer_user, viewer_membership, policy, invoice_due_7_days_ago):
        """Viewer role should not be able to approve reminders."""
        from django.test import RequestFactory
        from rest_framework.test import force_authenticate
        from reminders.views import ReminderJobViewSet
        
        job = ReminderJob.objects.create(
            organization=org,
            policy=policy,
            invoice=invoice_due_7_days_ago,
            customer=invoice_due_7_days_ago.customer,
            scheduled_date=date.today(),
            balance_at_scheduling_minor=118000,
            idempotency_key="test-perm",
            status=ReminderJob.Status.PROPOSED,
        )
        
        factory = RequestFactory()
        request = factory.post(f"/api/v1/reminders/jobs/{job.id}/approve/")
        force_authenticate(request, user=viewer_user)
        request.membership = viewer_membership
        
        view = ReminderJobViewSet.as_view({"post": "approve"})
        response = view(request, pk=str(job.id))
        
        assert response.status_code == 403
        job.refresh_from_db()
        assert job.status == ReminderJob.Status.PROPOSED  # Unchanged
