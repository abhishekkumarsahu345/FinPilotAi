"""
Tests for schedule management (toggle, archive, set_default).
Tests new fields is_default, archived on ReminderSchedule model.
Covers permissions, audit logs, and task filtering.
"""
import pytest
from datetime import date, timedelta
from django.contrib.auth import get_user_model

from core.models import Organization, Membership, AuditLog, Invoice, Customer
from reminders.models import (
    ReminderSchedule,
    ReminderStep,
    ReminderJob,
    ReminderTemplate,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def org():
    return Organization.objects.create(
        name="Acme Corp",
        timezone="Asia/Kolkata",
        business_email="finance@acme.in",
    )


@pytest.fixture
def owner(org):
    u = User.objects.create_user(
        username="owner1", email="owner@acme.in", password="pass"
    )
    Membership.objects.create(organization=org, user=u, role=Membership.Role.OWNER)
    return u


@pytest.fixture
def manager(org):
    u = User.objects.create_user(
        username="mgr1", email="mgr@acme.in", password="pass"
    )
    Membership.objects.create(organization=org, user=u, role=Membership.Role.MANAGER)
    return u


@pytest.fixture
def viewer(org):
    u = User.objects.create_user(
        username="viewer1", email="viewer@acme.in", password="pass"
    )
    Membership.objects.create(organization=org, user=u, role=Membership.Role.VIEWER)
    return u


@pytest.fixture
def template(org, owner):
    return ReminderTemplate.objects.create(
        organization=org,
        name="Friendly",
        channel="email",
        subject="Invoice {{invoice_number}}",
        body="Dear {{customer_name}}, pay {{outstanding_amount}} by {{due_date}}.",
        active=True,
        created_by=owner,
    )


@pytest.fixture
def schedule(org, owner, template):
    """Non-default schedule with 1 step."""
    sched = ReminderSchedule.objects.create(
        organization=org,
        name="Test Schedule",
        enabled=True,
        is_default=False,
        archived=False,
        created_by=owner,
    )
    ReminderStep.objects.create(
        schedule=sched,
        step_number=1,
        offset_from_due=0,
        offset_from_issue=None,
        tone="friendly",
        template=template,
        approval_mode=ReminderStep.ApprovalMode.MANUAL,
        enabled=True,
    )
    return sched


@pytest.fixture
def default_schedule(org, owner, template):
    """Schedule marked as default."""
    sched = ReminderSchedule.objects.create(
        organization=org,
        name="Default Schedule",
        enabled=True,
        is_default=True,
        archived=False,
        created_by=owner,
    )
    ReminderStep.objects.create(
        schedule=sched,
        step_number=1,
        offset_from_due=-7,
        offset_from_issue=None,
        tone="friendly",
        template=template,
        approval_mode=ReminderStep.ApprovalMode.MANUAL,
        enabled=True,
    )
    return sched


@pytest.fixture
def customer(org):
    return Customer.objects.create(
        organization=org,
        name="ACME Buyer",
        email="buyer@acmebiz.com",
        gstin="27AAAAA0000A1Z5",
    )


@pytest.fixture
def invoice(org, owner, customer):
    return Invoice.objects.create(
        organization=org,
        customer=customer,
        invoice_number="INV-001",
        invoice_date=date.today() - timedelta(days=30),
        due_date=date.today(),
        subtotal_minor=100000,
        total_minor=118000,
        status=Invoice.Status.ISSUED,
        created_by=owner,
    )


@pytest.fixture
def job(schedule, invoice, customer):
    """ReminderJob in PROPOSED status."""
    step = schedule.steps.first()
    return ReminderJob.objects.create(
        organization=schedule.organization,
        schedule=schedule,
        step=step,
        invoice=invoice,
        customer=customer,
        scheduled_date=date.today(),
        balance_at_scheduling_minor=118000,
        snapshot_total_minor=118000,
        snapshot_paid_minor=0,
        snapshot_outstanding_minor=118000,
        snapshot_due_date=invoice.due_date,
        snapshot_days_overdue=0,
        idempotency_key=f"{schedule.id}:{step.id}:{invoice.id}:today",
        status=ReminderJob.Status.PROPOSED,
    )


def _authed_client(user, org):
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return client


# ---------------------------------------------------------------------------
# Toggle tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestScheduleToggle:
    def test_owner_can_deactivate_schedule(self, org, owner, schedule):
        """Owner toggles schedule from enabled=True to False."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/toggle/"
        
        resp = client.post(url)
        assert resp.status_code == 200, resp.data
        assert resp.data["enabled"] is False
        
        schedule.refresh_from_db()
        assert schedule.enabled is False
    
    def test_owner_can_reactivate_schedule(self, org, owner, schedule):
        """Owner toggles disabled schedule back to enabled."""
        schedule.enabled = False
        schedule.save()
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/toggle/"
        
        resp = client.post(url)
        assert resp.status_code == 200
        assert resp.data["enabled"] is True
        
        schedule.refresh_from_db()
        assert schedule.enabled is True
    
    def test_viewer_cannot_toggle(self, org, viewer, schedule):
        """Viewer gets 403 when trying to toggle."""
        client = _authed_client(viewer, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/toggle/"
        
        resp = client.post(url)
        assert resp.status_code == 403
        
        schedule.refresh_from_db()
        assert schedule.enabled is True
    
    def test_cannot_deactivate_default_schedule(self, org, owner, default_schedule):
        """Cannot turn off a default schedule — returns 400."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{default_schedule.id}/toggle/"
        
        resp = client.post(url)
        assert resp.status_code == 400
        assert "default" in str(resp.data).lower()
        
        default_schedule.refresh_from_db()
        assert default_schedule.enabled is True
    
    def test_deactivating_does_not_cancel_jobs(self, org, owner, schedule, job):
        """Deactivating a schedule does NOT change existing proposed jobs."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/toggle/"
        
        resp = client.post(url)
        assert resp.status_code == 200
        
        job.refresh_from_db()
        assert job.status == ReminderJob.Status.PROPOSED
    
    def test_audit_log_created_for_toggle(self, org, owner, schedule):
        """Toggle creates an audit log entry."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/toggle/"
        
        client.post(url)
        
        log = AuditLog.objects.filter(
            organization=org,
            action="reminder_schedule.deactivated",
            entity_type="reminder_schedule",
            entity_id=str(schedule.id),
        ).first()
        assert log is not None
        assert schedule.name in log.summary


# ---------------------------------------------------------------------------
# Archive tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestScheduleArchive:
    def test_owner_can_archive_schedule(self, org, owner, schedule):
        """Owner archives a non-default schedule."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/archive/"
        
        resp = client.post(url)
        assert resp.status_code == 200, resp.data
        assert "archived" in str(resp.data).lower()
        
        schedule.refresh_from_db()
        assert schedule.archived is True
        assert schedule.enabled is False
    
    def test_archived_schedule_not_in_list(self, org, owner, schedule):
        """After archiving, schedule no longer appears in GET /schedules/."""
        client = _authed_client(owner, org)
        archive_url = f"/api/v1/reminders/schedules/{schedule.id}/archive/"
        
        client.post(archive_url)
        
        list_resp = client.get("/api/v1/reminders/schedules/")
        assert list_resp.status_code == 200
        ids = [s["id"] for s in list_resp.data["results"]]
        assert str(schedule.id) not in ids
    
    def test_archived_schedule_jobs_still_readable(self, org, owner, schedule, job):
        """Jobs under archived schedule still exist and are readable via direct query."""
        client = _authed_client(owner, org)
        archive_url = f"/api/v1/reminders/schedules/{schedule.id}/archive/"
        
        client.post(archive_url)
        
        # Job still exists in DB
        assert ReminderJob.objects.filter(id=job.id).exists()
        # Job detail endpoint still works (org scoping)
        job_resp = client.get(f"/api/v1/reminders/jobs/{job.id}/")
        assert job_resp.status_code == 200
    
    def test_cannot_archive_default_schedule(self, org, owner, default_schedule):
        """Archive endpoint rejects default schedule with 400."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{default_schedule.id}/archive/"
        
        resp = client.post(url)
        assert resp.status_code == 400
        assert "default" in str(resp.data).lower()
        
        default_schedule.refresh_from_db()
        assert default_schedule.archived is False
    
    def test_viewer_cannot_archive(self, org, viewer, schedule):
        """Viewer gets 403 when trying to archive."""
        client = _authed_client(viewer, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/archive/"
        
        resp = client.post(url)
        assert resp.status_code == 403
        
        schedule.refresh_from_db()
        assert schedule.archived is False
    
    def test_audit_log_created_for_archive(self, org, owner, schedule):
        """Archive creates an audit log entry."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/archive/"
        
        client.post(url)
        
        log = AuditLog.objects.filter(
            organization=org,
            action="reminder_schedule.archived",
            entity_type="reminder_schedule",
            entity_id=str(schedule.id),
        ).first()
        assert log is not None
        assert schedule.name in log.summary
    
    def test_archive_impact_endpoint(self, org, owner, schedule, job):
        """archive-impact returns correct job/invoice count."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/archive-impact/"
        
        resp = client.get(url)
        assert resp.status_code == 200
        assert resp.data["schedule_name"] == schedule.name
        assert resp.data["live_jobs"] == 1
        assert resp.data["invoices_affected"] == 1


# ---------------------------------------------------------------------------
# Default schedule tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestScheduleDefault:
    def test_owner_can_set_schedule_as_default(self, org, owner, schedule):
        """Owner sets a schedule as default."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/set-default/"
        
        resp = client.post(url)
        assert resp.status_code == 200
        assert resp.data["is_default"] is True
        
        schedule.refresh_from_db()
        assert schedule.is_default is True
    
    def test_only_one_default_per_org(self, org, owner, schedule, default_schedule):
        """Setting a new default unsets the old one."""
        # default_schedule is currently the default
        assert default_schedule.is_default is True
        
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/set-default/"
        
        resp = client.post(url)
        assert resp.status_code == 200
        
        schedule.refresh_from_db()
        default_schedule.refresh_from_db()
        
        assert schedule.is_default is True
        assert default_schedule.is_default is False
    
    def test_viewer_cannot_set_default(self, org, viewer, schedule):
        """Viewer gets 403."""
        client = _authed_client(viewer, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/set-default/"
        
        resp = client.post(url)
        assert resp.status_code == 403
        
        schedule.refresh_from_db()
        assert schedule.is_default is False
    
    def test_cannot_set_archived_schedule_as_default(self, org, owner, schedule):
        """Cannot set an archived schedule as default."""
        schedule.archived = True
        schedule.save()
        
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/set-default/"
        
        resp = client.post(url)
        assert resp.status_code == 400
        assert "archived" in str(resp.data).lower()
        
        schedule.refresh_from_db()
        assert schedule.is_default is False
    
    def test_cannot_deactivate_default_schedule_via_toggle(
        self, org, owner, default_schedule
    ):
        """Toggle endpoint rejects deactivating a default schedule."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{default_schedule.id}/toggle/"
        
        resp = client.post(url)
        assert resp.status_code == 400
        assert "default" in str(resp.data).lower()
    
    def test_cannot_archive_default_schedule_via_archive(
        self, org, owner, default_schedule
    ):
        """Archive endpoint rejects default schedule."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{default_schedule.id}/archive/"
        
        resp = client.post(url)
        assert resp.status_code == 400
        assert "default" in str(resp.data).lower()
    
    def test_audit_log_created_for_set_default(self, org, owner, schedule):
        """set-default creates an audit log entry."""
        client = _authed_client(owner, org)
        url = f"/api/v1/reminders/schedules/{schedule.id}/set-default/"
        
        client.post(url)
        
        log = AuditLog.objects.filter(
            organization=org,
            action="reminder_schedule.set_default",
            entity_type="reminder_schedule",
            entity_id=str(schedule.id),
        ).first()
        assert log is not None
        assert schedule.name in log.summary


# ---------------------------------------------------------------------------
# Task integration tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestScheduleTaskFiltering:
    def test_schedule_step_reminders_skips_archived(self, org, owner, schedule):
        """Celery task skips archived schedules."""
        from reminders.schedule_tasks import schedule_step_reminders
        
        # Archive the schedule
        schedule.archived = True
        schedule.save()
        
        # Task should not error, should just skip the archived schedule
        result = schedule_step_reminders()
        assert result["scheduled"] == 0
    
    def test_schedule_step_reminders_skips_disabled(self, org, owner, schedule):
        """Celery task skips disabled schedules."""
        from reminders.schedule_tasks import schedule_step_reminders
        
        # Disable the schedule
        schedule.enabled = False
        schedule.save()
        
        result = schedule_step_reminders()
        assert result["scheduled"] == 0
