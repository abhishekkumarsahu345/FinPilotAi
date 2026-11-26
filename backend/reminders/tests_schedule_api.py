"""
Tests for ReminderSchedule create/edit via the with-steps API endpoint.
Covers: create, edit, validation, permissions, org scoping, audit log.
"""
import pytest
from django.contrib.auth import get_user_model

from core.models import Organization, Membership, AuditLog
from reminders.models import ReminderTemplate, ReminderSchedule, ReminderStep

User = get_user_model()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def org():
    return Organization.objects.create(
        name="Acme Org",
        timezone="Asia/Kolkata",
        business_email="finance@acme.in",
    )


@pytest.fixture
def org2():
    return Organization.objects.create(
        name="Other Org",
        timezone="Asia/Kolkata",
    )


@pytest.fixture
def owner(org):
    u = User.objects.create_user(username="owner1", email="owner@acme.in", password="pass")
    Membership.objects.create(organization=org, user=u, role=Membership.Role.OWNER)
    return u


@pytest.fixture
def manager(org):
    u = User.objects.create_user(username="mgr1", email="mgr@acme.in", password="pass")
    Membership.objects.create(organization=org, user=u, role="manager")
    return u


@pytest.fixture
def viewer(org):
    u = User.objects.create_user(username="viewer1", email="viewer@acme.in", password="pass")
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
def template2(org, owner):
    return ReminderTemplate.objects.create(
        organization=org,
        name="Firm",
        channel="email",
        subject="Overdue: {{invoice_number}}",
        body="Your invoice {{invoice_number}} is overdue.",
        active=True,
        created_by=owner,
    )


@pytest.fixture
def inactive_template(org, owner):
    return ReminderTemplate.objects.create(
        organization=org,
        name="Inactive",
        channel="email",
        subject="Subject",
        body="Body {{invoice_number}}.",
        active=False,
        created_by=owner,
    )


@pytest.fixture
def wa_template(org, owner):
    return ReminderTemplate.objects.create(
        organization=org,
        name="WA Template",
        channel="whatsapp",
        subject="",
        body="Hi {{customer_name}}",
        active=True,
        created_by=owner,
    )


def _authed_client(user, org):
    """Return a DRF APIClient authenticated as user, with org header."""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=user)
    client.defaults["HTTP_X_ORGANIZATION_ID"] = str(org.id)
    return client


CREATE_URL = "/api/v1/reminders/schedules/with-steps/"


def edit_url(schedule_id):
    return f"/api/v1/reminders/schedules/{schedule_id}/with-steps/"


# ---------------------------------------------------------------------------
# Create tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestScheduleCreate:
    def test_owner_can_create_schedule_with_steps(self, org, owner, template):
        client = _authed_client(owner, org)
        payload = {
            "name": "My Schedule",
            "steps": [
                {"basis": "issue", "kind": "on", "days": 0, "template": str(template.id)},
                {"basis": "due", "kind": "before", "days": 7, "template": str(template.id)},
                {"basis": "due", "kind": "after", "days": 3, "template": str(template.id)},
            ],
        }
        resp = client.post(CREATE_URL, payload, format="json")
        assert resp.status_code == 201, resp.data
        data = resp.data
        assert data["name"] == "My Schedule"
        assert data["step_count"] == 3

        schedule = ReminderSchedule.objects.get(id=data["id"])
        assert schedule.organization == org
        steps = list(schedule.steps.order_by("step_number"))
        assert len(steps) == 3
        assert steps[0].offset_from_issue == 0
        assert steps[0].offset_from_due is None
        assert steps[1].offset_from_due == -7     # before = negative
        assert steps[2].offset_from_due == 3      # after = positive
        # All steps default to manual approval
        for s in steps:
            assert s.approval_mode == ReminderStep.ApprovalMode.MANUAL

    def test_manager_can_create_schedule(self, org, manager, template):
        client = _authed_client(manager, org)
        payload = {
            "name": "Manager Schedule",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }
        resp = client.post(CREATE_URL, payload, format="json")
        assert resp.status_code == 201

    def test_new_schedule_appears_in_list(self, org, owner, template):
        client = _authed_client(owner, org)
        client.post(CREATE_URL, {
            "name": "List Schedule",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        list_resp = client.get("/api/v1/reminders/schedules/")
        assert list_resp.status_code == 200
        names = [s["name"] for s in list_resp.data["results"]]
        assert "List Schedule" in names

    def test_audit_log_entry_created(self, org, owner, template):
        client = _authed_client(owner, org)
        client.post(CREATE_URL, {
            "name": "Audit Schedule",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert AuditLog.objects.filter(
            organization=org,
            action="reminder_schedule.created",
            actor=owner,
        ).exists()

    def test_on_due_date_step(self, org, owner, template):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "On Due",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert resp.status_code == 201
        step = ReminderStep.objects.get(schedule__id=resp.data["id"])
        assert step.offset_from_due == 0

    def test_last_step_marked_final_notice(self, org, owner, template):
        """The last step with offset_from_due > 0 should be marked as final notice."""
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "Final",
            "steps": [
                {"basis": "due", "kind": "before", "days": 7, "template": str(template.id)},
                {"basis": "due", "kind": "after", "days": 15, "template": str(template.id)},
            ],
        }, format="json")
        assert resp.status_code == 201
        steps = list(ReminderStep.objects.filter(schedule__id=resp.data["id"]).order_by("step_number"))
        assert steps[0].is_final_notice is False
        assert steps[1].is_final_notice is True


# ---------------------------------------------------------------------------
# Edit tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestScheduleEdit:
    def test_owner_can_rename_schedule(self, org, owner, template):
        client = _authed_client(owner, org)
        create_resp = client.post(CREATE_URL, {
            "name": "Old Name",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        sid = create_resp.data["id"]

        edit_resp = client.put(edit_url(sid), {
            "name": "New Name",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert edit_resp.status_code == 200
        assert edit_resp.data["name"] == "New Name"
        assert ReminderSchedule.objects.get(id=sid).name == "New Name"

    def test_edit_replaces_steps(self, org, owner, template, template2):
        client = _authed_client(owner, org)
        create_resp = client.post(CREATE_URL, {
            "name": "Sched",
            "steps": [
                {"basis": "due", "kind": "before", "days": 7, "template": str(template.id)},
                {"basis": "due", "kind": "after", "days": 3, "template": str(template.id)},
            ],
        }, format="json")
        sid = create_resp.data["id"]

        edit_resp = client.put(edit_url(sid), {
            "name": "Sched",
            "steps": [
                {"basis": "due", "kind": "on", "days": 0, "template": str(template2.id)},
            ],
        }, format="json")
        assert edit_resp.status_code == 200
        active_steps = list(ReminderStep.objects.filter(
            schedule__id=sid, enabled=True
        ).order_by("step_number"))
        assert len(active_steps) == 1
        assert active_steps[0].offset_from_due == 0
        assert active_steps[0].template == template2

    def test_edit_preserves_step_row_for_unchanged_timing(self, org, owner, template, template2):
        """Steps with the same timing keep their DB id after edit."""
        client = _authed_client(owner, org)
        create_resp = client.post(CREATE_URL, {
            "name": "Sched",
            "steps": [{"basis": "due", "kind": "before", "days": 7, "template": str(template.id)}],
        }, format="json")
        sid = create_resp.data["id"]
        original_step_id = ReminderStep.objects.get(schedule__id=sid).id

        client.put(edit_url(sid), {
            "name": "Sched",
            "steps": [{"basis": "due", "kind": "before", "days": 7, "template": str(template2.id)}],
        }, format="json")
        # Same timing → same DB row
        same_step = ReminderStep.objects.get(id=original_step_id)
        assert same_step.template == template2

    def test_edit_audit_log(self, org, owner, template):
        client = _authed_client(owner, org)
        create_resp = client.post(CREATE_URL, {
            "name": "AL Sched",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        sid = create_resp.data["id"]
        client.put(edit_url(sid), {
            "name": "AL Sched Updated",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert AuditLog.objects.filter(
            organization=org, action="reminder_schedule.updated", actor=owner
        ).exists()


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestScheduleValidation:
    def test_name_required(self, org, owner, template):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert resp.status_code == 400
        assert "name" in str(resp.data).lower() or "required" in str(resp.data).lower()

    def test_at_least_one_step_required(self, org, owner):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {"name": "X", "steps": []}, format="json")
        assert resp.status_code == 400

    def test_max_10_steps(self, org, owner, template):
        client = _authed_client(owner, org)
        steps = [{"basis": "due", "kind": "after", "days": i + 1, "template": str(template.id)}
                 for i in range(11)]
        resp = client.post(CREATE_URL, {"name": "X", "steps": steps}, format="json")
        assert resp.status_code == 400

    def test_duplicate_timing_rejected(self, org, owner, template):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "Dup",
            "steps": [
                {"basis": "due", "kind": "before", "days": 7, "template": str(template.id)},
                {"basis": "due", "kind": "before", "days": 7, "template": str(template.id)},
            ],
        }, format="json")
        assert resp.status_code == 400
        assert "timing" in str(resp.data).lower() or "different" in str(resp.data).lower()

    def test_template_must_belong_to_org(self, org, org2, owner):
        """Template from a different org must be rejected."""
        other_user = User.objects.create_user(username="other99", email="o99@test.com", password="pass")
        Membership.objects.create(organization=org2, user=other_user, role=Membership.Role.OWNER)
        other_tmpl = ReminderTemplate.objects.create(
            organization=org2,
            name="Other Tmpl",
            channel="email",
            subject="Subj {{invoice_number}}",
            body="Body {{invoice_number}} {{customer_name}} {{outstanding_amount}} {{due_date}}.",
            active=True,
            created_by=other_user,
        )
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "X",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(other_tmpl.id)}],
        }, format="json")
        assert resp.status_code == 400

    def test_inactive_template_rejected(self, org, owner, inactive_template):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "X",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(inactive_template.id)}],
        }, format="json")
        assert resp.status_code == 400
        assert "inactive" in str(resp.data).lower()

    def test_whatsapp_template_rejected(self, org, owner, wa_template):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "X",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(wa_template.id)}],
        }, format="json")
        assert resp.status_code == 400
        assert "email" in str(resp.data).lower()

    def test_days_before_must_be_positive(self, org, owner, template):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "X",
            "steps": [{"basis": "due", "kind": "before", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert resp.status_code == 400

    def test_days_after_must_be_positive(self, org, owner, template):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "X",
            "steps": [{"basis": "due", "kind": "after", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert resp.status_code == 400

    def test_days_exceeding_365_rejected(self, org, owner, template):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "X",
            "steps": [{"basis": "due", "kind": "after", "days": 400, "template": str(template.id)}],
        }, format="json")
        assert resp.status_code == 400

    def test_invalid_basis_rejected(self, org, owner, template):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "X",
            "steps": [{"basis": "banana", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert resp.status_code == 400

    def test_missing_template_rejected(self, org, owner):
        client = _authed_client(owner, org)
        resp = client.post(CREATE_URL, {
            "name": "X",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": ""}],
        }, format="json")
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Permission tests
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestSchedulePermissions:
    def test_viewer_cannot_create(self, org, viewer, template):
        client = _authed_client(viewer, org)
        resp = client.post(CREATE_URL, {
            "name": "X",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert resp.status_code == 403

    def test_viewer_cannot_edit(self, org, owner, viewer, template):
        owner_client = _authed_client(owner, org)
        create_resp = owner_client.post(CREATE_URL, {
            "name": "Perm Sched",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        sid = create_resp.data["id"]

        viewer_client = _authed_client(viewer, org)
        resp = viewer_client.put(edit_url(sid), {
            "name": "Hacked",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        assert resp.status_code == 403
        assert ReminderSchedule.objects.get(id=sid).name == "Perm Sched"

    def test_unauthenticated_cannot_create(self):
        from rest_framework.test import APIClient
        client = APIClient()
        resp = client.post(CREATE_URL, {"name": "X", "steps": []}, format="json")
        assert resp.status_code in (401, 403)

    def test_other_org_cannot_edit(self, org, org2, owner, template):
        """A user from org2 must not be able to edit org's schedule."""
        # Create schedule in org
        owner_client = _authed_client(owner, org)
        create_resp = owner_client.post(CREATE_URL, {
            "name": "Org1 Sched",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")
        sid = create_resp.data["id"]

        # Create user in org2
        other_user = User.objects.create_user(username="other_owner2", email="o2@test.com", password="pass")
        Membership.objects.create(organization=org2, user=other_user, role=Membership.Role.OWNER)
        other_tmpl = ReminderTemplate.objects.create(
            organization=org2, name="Tmpl2", channel="email",
            subject="S {{invoice_number}}", body="B {{customer_name}} {{invoice_number}} {{outstanding_amount}} {{due_date}}.",
            active=True, created_by=other_user,
        )
        other_client = _authed_client(other_user, org2)
        resp = other_client.put(edit_url(sid), {
            "name": "Stolen",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(other_tmpl.id)}],
        }, format="json")
        assert resp.status_code in (403, 404)
        assert ReminderSchedule.objects.get(id=sid).name == "Org1 Sched"

    def test_org_scoping_schedules_list(self, org, org2, owner, template):
        """List endpoint only returns schedules from the authenticated org."""
        # Create in org1
        c1 = _authed_client(owner, org)
        c1.post(CREATE_URL, {
            "name": "Org1 Schedule",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(template.id)}],
        }, format="json")

        # Create in org2
        other_user = User.objects.create_user(username="other_owner3", email="o3@test.com", password="pass")
        Membership.objects.create(organization=org2, user=other_user, role=Membership.Role.OWNER)
        other_tmpl = ReminderTemplate.objects.create(
            organization=org2, name="OT", channel="email",
            subject="S {{invoice_number}}", body="B {{customer_name}} {{invoice_number}} {{outstanding_amount}} {{due_date}}.",
            active=True, created_by=other_user,
        )
        c2 = _authed_client(other_user, org2)
        c2.post(CREATE_URL, {
            "name": "Org2 Schedule",
            "steps": [{"basis": "due", "kind": "on", "days": 0, "template": str(other_tmpl.id)}],
        }, format="json")

        # Org1 user should only see Org1's schedule
        list_resp = c1.get("/api/v1/reminders/schedules/")
        names = [s["name"] for s in list_resp.data["results"]]
        assert "Org1 Schedule" in names
        assert "Org2 Schedule" not in names
