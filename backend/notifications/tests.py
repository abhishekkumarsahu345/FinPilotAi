"""
Tests for the notifications API, including live enrichment of details.
"""
import uuid
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import (
    Customer,
    Invoice,
    Membership,
    Organization,
    Payment,
    PaymentAllocation,
)
from imports_app.models import ImportBatch
from notifications.models import Notification

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def org():
    return Organization.objects.create(
        name="Test Org",
        timezone="Asia/Kolkata",
        business_email="finance@testorg.in",
    )


@pytest.fixture
def owner_user():
    return User.objects.create_user(
        username="notif_owner",
        email="notif_owner@test.com",
        password="pass",
    )


@pytest.fixture
def owner_membership(org, owner_user):
    return Membership.objects.create(
        organization=org,
        user=owner_user,
        role=Membership.Role.OWNER,
        active=True,
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
def invoice(org, customer, owner_user):
    return Invoice.objects.create(
        organization=org,
        customer=customer,
        invoice_number="INV-TEST-001",
        invoice_date=date.today() - timedelta(days=30),
        due_date=date.today() - timedelta(days=5),
        currency="INR",
        subtotal_minor=100000,
        discount_minor=0,
        tax_minor=18000,
        total_minor=118000,
        status=Invoice.Status.ISSUED,
        created_by=owner_user,
    )


@pytest.fixture
def reminder_step(org, owner_user):
    """Create a ReminderSchedule + ReminderStep for enrichment."""
    from reminders.models import ReminderSchedule, ReminderStep, ReminderTemplate

    template = ReminderTemplate.objects.create(
        organization=org,
        name="Test Template",
        channel="email",
        subject="Invoice {{invoice_number}} due",
        body="Dear {{customer_name}},",
        created_by=owner_user,
    )
    schedule = ReminderSchedule.objects.create(
        organization=org,
        name="Default Schedule",
        enabled=True,
        created_by=owner_user,
    )
    step = ReminderStep.objects.create(
        schedule=schedule,
        step_number=2,
        offset_from_due=3,   # 3 days after due
        tone=ReminderStep.Tone.FRIENDLY,
        template=template,
        approval_mode=ReminderStep.ApprovalMode.MANUAL,
        enabled=True,
    )
    return step


@pytest.fixture
def reminder_job(org, invoice, customer, reminder_step, owner_user):
    from reminders.models import ReminderJob

    return ReminderJob.objects.create(
        organization=org,
        schedule=reminder_step.schedule,
        step=reminder_step,
        invoice=invoice,
        customer=customer,
        scheduled_date=date.today(),
        balance_at_scheduling_minor=118000,
        snapshot_total_minor=118000,
        snapshot_paid_minor=0,
        snapshot_outstanding_minor=118000,
        snapshot_due_date=invoice.due_date,
        snapshot_days_overdue=5,
        snapshot_created_at=timezone.now(),
        idempotency_key=f"test-notif:{uuid.uuid4()}",
        status="proposed",
    )


@pytest.fixture
def import_batch(org, owner_user):
    return ImportBatch.objects.create(
        organization=org,
        batch_type=ImportBatch.BatchType.INVOICE,
        file_name="invoices_jan.xlsx",
        status=ImportBatch.Status.COMMITTED,
        rows_total=10,
        rows_valid=9,
        rows_created=9,
        rows_rejected=1,
        created_by=owner_user,
    )


@pytest.fixture
def api_client(owner_user, owner_membership):
    """API client authenticated as owner, with org header."""
    client = APIClient()
    client.force_authenticate(user=owner_user)
    client.credentials(HTTP_X_ORGANIZATION_ID=str(owner_membership.organization_id))
    return client


# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestReminderApprovalEnrichment:

    def test_reminder_approval_details(self, org, owner_user, owner_membership, reminder_job, api_client):
        """reminder_approval notification should include full job snapshot details."""
        Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.REMINDER_AWAITING_APPROVAL,
            entity_type="reminder_job",
            entity_id=str(reminder_job.id),
            payload={},
        )

        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        notifications = resp.data["notifications"]
        assert len(notifications) == 1
        details = notifications[0]["details"]
        assert details["customer_name"] == "Acme Corp"
        assert details["invoice_number"] == "INV-TEST-001"
        assert details["outstanding_minor"] == 118000
        assert details["days_overdue"] == 5
        assert details["step_label"] == "3 days after due"
        assert "job_status" in details
        # block_reason must be absent (None) for approval notifications
        assert details["block_reason"] is None

    def test_reminder_failed_details(self, org, owner_user, owner_membership, reminder_job, api_client):
        """reminder_failed notification should include block_reason."""
        from reminders.models import ReminderJob

        reminder_job.status = ReminderJob.Status.FAILED
        reminder_job.block_reason = "SMTP connection refused"
        reminder_job.save()

        Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.REMINDER_FAILED,
            entity_type="reminder_job",
            entity_id=str(reminder_job.id),
            payload={},
        )

        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        details = resp.data["notifications"][0]["details"]
        assert details["block_reason"] == "SMTP connection refused"
        assert details["customer_name"] == "Acme Corp"


@pytest.mark.django_db
class TestImportEnrichment:

    def test_import_complete_details(self, org, owner_user, owner_membership, import_batch, api_client):
        """import_complete notification should include file_name and rows_created."""
        Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.IMPORT_COMPLETE,
            entity_type="import_batch",
            entity_id=str(import_batch.id),
            payload={},
        )

        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        details = resp.data["notifications"][0]["details"]
        assert details["file_name"] == "invoices_jan.xlsx"
        assert details["rows_created"] == 9
        assert details["rows_rejected"] == 1
        assert details["status"] == ImportBatch.Status.COMMITTED


@pytest.mark.django_db
class TestReconciliationEnrichment:

    def test_reconciliation_review_details(self, org, owner_user, owner_membership, import_batch, api_client):
        """reconciliation_review notification should include live unmatched_count."""
        from reconciliation.models import BankTransaction

        # Create 3 unmatched bank transactions
        for i in range(3):
            BankTransaction.objects.create(
                organization=org,
                import_batch=import_batch,
                transaction_date=date.today(),
                credit_minor=50000,
                reconciliation_status=BankTransaction.ReconciliationStatus.UNMATCHED,
            )

        Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.RECONCILIATION_REVIEW,
            entity_type="",
            entity_id="",
            payload={},
        )

        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        details = resp.data["notifications"][0]["details"]
        assert details["unmatched_count"] == 3
        assert "suggested_count" in details


@pytest.mark.django_db
class TestFallbacks:

    def test_missing_entity_fallback(self, org, owner_user, owner_membership, api_client):
        """Notification referencing a non-existent entity_id returns details_unavailable, not 500."""
        Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.REMINDER_AWAITING_APPROVAL,
            entity_type="reminder_job",
            entity_id=str(uuid.uuid4()),  # does not exist
            payload={},
        )

        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        details = resp.data["notifications"][0]["details"]
        assert details == {"error": "details_unavailable"}

    def test_old_notification_no_entity_fallback(self, org, owner_user, owner_membership, api_client):
        """Old-format notification with empty entity_type/entity_id returns empty details dict."""
        Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.SECURITY_EVENT,
            entity_type="",
            entity_id="",
            payload={"note": "login from new device"},
        )

        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        details = resp.data["notifications"][0]["details"]
        assert details == {}


@pytest.mark.django_db
class TestMarkRead:

    def test_mark_read_on_click(self, org, owner_user, owner_membership, api_client):
        """POST to mark-read endpoint returns 200 and marks the notification read."""
        notif = Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.SECURITY_EVENT,
            entity_type="",
            entity_id="",
            payload={},
        )
        assert notif.read_at is None

        resp = api_client.post(f"/api/v1/notifications/{notif.id}/read/")
        assert resp.status_code == 200

        notif.refresh_from_db()
        assert notif.read_at is not None


@pytest.mark.django_db
class TestOrgIsolation:

    def test_org_isolation(self, org, owner_user, owner_membership, reminder_job, api_client):
        """Notifications belonging to org2 must not appear in org1's list."""
        org2 = Organization.objects.create(
            name="Org Two",
            timezone="Asia/Kolkata",
        )
        user2 = User.objects.create_user(
            username="user2_notif",
            email="user2@notif.test",
            password="pass",
        )
        Membership.objects.create(
            organization=org2, user=user2, role=Membership.Role.OWNER, active=True
        )

        # Create a notification for org2
        Notification.objects.create(
            organization=org2,
            recipient=user2,
            event_type=Notification.EventType.SECURITY_EVENT,
            entity_type="",
            entity_id="",
            payload={},
        )

        # Create a notification for org1 owner
        Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.SECURITY_EVENT,
            entity_type="",
            entity_id="",
            payload={"mine": True},
        )

        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        notifications = resp.data["notifications"]
        # Only org1's notification appears
        assert len(notifications) == 1
        assert notifications[0]["payload"]["mine"] is True


@pytest.mark.django_db
class TestJobStatusEdgeCases:

    def test_already_dispatched_job_details_still_returned(
        self, org, owner_user, owner_membership, reminder_job, api_client
    ):
        """
        A reminder_approval notification for an already-dispatched job should
        still return details (not an error).
        """
        from reminders.models import ReminderJob

        reminder_job.status = ReminderJob.Status.DISPATCHED
        reminder_job.dispatched_at = timezone.now()
        reminder_job.save()

        Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.REMINDER_AWAITING_APPROVAL,
            entity_type="reminder_job",
            entity_id=str(reminder_job.id),
            payload={},
        )

        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        details = resp.data["notifications"][0]["details"]
        assert details.get("job_status") == "dispatched"
        assert "error" not in details

    def test_paid_invoice_job_details_show_snapshot(
        self, org, owner_user, owner_membership, invoice, reminder_job, api_client
    ):
        """
        When invoice is fully paid after the job was created, the endpoint
        returns 200 and the SNAPSHOT outstanding_minor (not live balance).
        """
        # Pay the invoice fully
        payment = Payment.objects.create(
            organization=org,
            customer=invoice.customer,
            payment_date=date.today(),
            amount_minor=118000,
            method=Payment.Method.BANK_TRANSFER,
            recorded_by=owner_user,
        )
        PaymentAllocation.objects.create(
            organization=org,
            payment=payment,
            invoice=invoice,
            amount_minor=118000,
            created_by=owner_user,
        )

        # reminder_job snapshot_outstanding_minor is still 118000 (snapshot)
        Notification.objects.create(
            organization=org,
            recipient=owner_user,
            event_type=Notification.EventType.REMINDER_AWAITING_APPROVAL,
            entity_type="reminder_job",
            entity_id=str(reminder_job.id),
            payload={},
        )

        resp = api_client.get("/api/v1/notifications/")
        assert resp.status_code == 200
        details = resp.data["notifications"][0]["details"]
        # Snapshot value is returned as-is; no crash
        assert details["outstanding_minor"] == 118000  # snapshot, not live 0
        assert "error" not in details
