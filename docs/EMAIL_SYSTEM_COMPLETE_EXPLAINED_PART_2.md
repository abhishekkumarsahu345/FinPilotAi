# FinPilot AI — Email & Reminder System: Complete Explanation (Part 2 of 2)

> **Coverage:** Sections 6–10 (API Reference, Configuration, Safety Rules, Known Limitations, Glossary)
> **Part 1** covers: Overview, File Structure, Full Source Code, Complete Flows, Database.

---

## 6. API Reference

All endpoints are under the prefix `/api/v1/`. All require an authenticated session cookie and an `X-Organization-ID` header. All use JSON. All paginate list responses with `{"count": N, "results": [...]}`.

FINANCE_ROLES required for write operations = `["owner", "manager"]` (defined in `core/permissions.py`).

---

### 6.1 Reminder Templates

#### `GET /api/v1/reminders/templates/`
List all templates for the current organization.

**Response:**
```json
{
  "count": 2,
  "results": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "Friendly Payment Reminder",
      "channel": "email",
      "subject": "Payment Reminder: Invoice {{invoice_number}}",
      "body": "Hello {{customer_name}}, ...",
      "active": true,
      "pending_revision": false,
      "created_at": "2025-01-10T09:00:00Z",
      "updated_at": "2025-01-10T09:00:00Z"
    }
  ]
}
```

#### `POST /api/v1/reminders/templates/`
Create a new template. Requires FINANCE_ROLES.

**Request body:**
```json
{
  "name": "My Template",
  "channel": "email",
  "subject": "Invoice {{invoice_number}} reminder",
  "body": "Dear {{customer_name}}, ..."
}
```

**Validation errors returned as 400:**
- Subject over 998 chars
- Body over 100,000 chars (email) or 4096 chars (whatsapp)
- Any `{{unsupported_placeholder}}` in subject or body

#### `PUT/PATCH /api/v1/reminders/templates/{id}/`
Update a template. If the template has active policies/steps, changing `body` or `subject` saves a `ReminderTemplateRevision` and sets `pending_revision=True`.

#### `POST /api/v1/reminders/templates/{id}/approve-revision/`
Clear `pending_revision`. Requires FINANCE_ROLES.

**Response:** `{"detail": "Revision approved."}`

---

### 6.2 Reminder Schedules (new system)

#### `GET /api/v1/reminders/schedules/`
List all non-archived schedules for the current org.

**Response:**
```json
{
  "count": 1,
  "results": [
    {
      "id": "a1b2c3d4-...",
      "name": "Standard Payment Reminders",
      "enabled": true,
      "is_default": true,
      "archived": false,
      "send_hour_start": 10,
      "send_hour_end": 18,
      "skip_weekdays": [5, 6],
      "excluded_customer_ids": [],
      "step_count": 4,
      "steps": [
        {
          "id": "step-uuid-1",
          "schedule": "a1b2c3d4-...",
          "step_number": 1,
          "offset_from_issue": 0,
          "offset_from_due": null,
          "tone": "issue",
          "tone_display": "Invoice Issue Notification",
          "template": "template-uuid-1",
          "template_name": "Invoice Issue Notification",
          "approval_mode": "manual",
          "approval_mode_display": "Approval Required",
          "auto_mode_confirmed_by": null,
          "enabled": true,
          "is_final_notice": false,
          "created_at": "2025-01-10T09:00:00Z"
        }
      ],
      "created_at": "2025-01-10T09:00:00Z",
      "updated_at": "2025-01-10T09:00:00Z"
    }
  ]
}
```

#### `POST /api/v1/reminders/schedules/with-steps/`
Create a schedule and all its steps in one atomic request. Requires FINANCE_ROLES.

**Request body:**
```json
{
  "name": "My Schedule",
  "steps": [
    {"basis": "issue", "kind": "on", "days": 0, "template": "template-uuid-1"},
    {"basis": "due", "kind": "before", "days": 7, "template": "template-uuid-2"},
    {"basis": "due", "kind": "after", "days": 3, "template": "template-uuid-3"},
    {"basis": "due", "kind": "after", "days": 15, "template": "template-uuid-4"}
  ]
}
```

`basis`: `"issue"` (relative to invoice date) or `"due"` (relative to due date).
`kind`: `"on"` (days ignored), `"before"` (days must be ≥1), `"after"` (days must be ≥1). Only for `basis=due`.
`days`: integer 0–365.
`template`: UUID of an active email template belonging to this org.

**Response:** `201 Created` — full `ReminderSchedule` object including embedded steps.

**Validation errors (400):**
```json
{"steps.0": "Step 1: a message template must be selected."}
{"steps": "Two steps are both set to send on the due date. Each step must have a different timing."}
```

#### `PUT /api/v1/reminders/schedules/{id}/with-steps/`
Replace the schedule name and full step list atomically. Same body shape as create. Requires FINANCE_ROLES.

#### `POST /api/v1/reminders/schedules/{id}/toggle/`
Activate or deactivate a schedule. Requires FINANCE_ROLES.
Blocked if `is_default=True` and currently enabled.

**Response:** Updated `ReminderSchedule` object.

#### `GET /api/v1/reminders/schedules/{id}/archive-impact/`
Preview the impact before archiving.

**Response:**
```json
{
  "schedule_id": "a1b2c3d4-...",
  "schedule_name": "Standard Payment Reminders",
  "is_default": false,
  "live_jobs": 12,
  "invoices_affected": 5
}
```

#### `POST /api/v1/reminders/schedules/{id}/archive/`
Soft-delete a schedule (`archived=True`, `enabled=False`). Requires FINANCE_ROLES. Blocked if `is_default=True`.

**Response:**
```json
{
  "detail": "Schedule 'Standard Payment Reminders' has been archived.",
  "live_jobs_cancelled": 12,
  "invoices_affected": 5
}
```

#### `POST /api/v1/reminders/schedules/{id}/set-default/`
Make this schedule the org's default. Requires FINANCE_ROLES. Blocked if archived.

**Response:** Updated `ReminderSchedule` object.

---

### 6.3 Reminder Steps

#### `GET /api/v1/reminders/steps/?schedule={schedule_id}`
List all steps (optionally filtered by schedule). Steps from any schedule in the org are accessible.

#### `POST /api/v1/reminders/steps/`
Add a step to an existing schedule.

**Request body:**
```json
{
  "schedule": "schedule-uuid",
  "step_number": 3,
  "offset_from_due": 7,
  "tone": "gentle",
  "template": "template-uuid",
  "approval_mode": "manual",
  "enabled": true,
  "is_final_notice": false
}
```

Either `offset_from_issue` or `offset_from_due` must be provided, not both.

#### `POST /api/v1/reminders/steps/{id}/activate-auto/`
Enable automatic sending for a step. Requires FINANCE_ROLES.

**Request body:** `{"confirm": true}` (required)

**Response:** `{"detail": "Automatic sending mode activated for this step."}`

#### `POST /api/v1/reminders/steps/{id}/deactivate-auto/`
Revert step to manual approval mode.

**Response:** `{"detail": "Automatic sending mode deactivated for this step."}`

---

### 6.4 Reminder Jobs (new system — `/jobs-v2/`)

#### `GET /api/v1/reminders/jobs-v2/`
List reminder jobs. Supports filtering by `status`, `invoice`, `schedule`, `step`, `needs_manual_followup`.

**Query params:**
- `?status=proposed` — pending approvals
- `?status=dispatched` — sent history
- `?status=failed` — failed deliveries
- `?include_preview=true` — adds `email_preview_html` to each job (expensive; use only for single-job views)

**Response (abbreviated):**
```json
{
  "count": 3,
  "results": [
    {
      "id": "job-uuid-1",
      "schedule": "schedule-uuid",
      "schedule_name": "Standard Payment Reminders",
      "step": "step-uuid-1",
      "step_number": 2,
      "step_tone": "friendly",
      "invoice": "invoice-uuid",
      "invoice_number": "INV-2025-042",
      "customer": "customer-uuid",
      "customer_name": "Acme Pvt Ltd",
      "customer_email": "accounts@acme.com",
      "scheduled_date": "2025-07-03",
      "status": "proposed",
      "status_display": "Awaiting Approval",
      "snapshot_total_minor": 1180000,
      "snapshot_paid_minor": 0,
      "snapshot_outstanding_minor": 1180000,
      "snapshot_due_date": "2025-07-10",
      "snapshot_days_overdue": 0,
      "snapshot_created_at": "2025-07-03T05:30:00Z",
      "current_outstanding_minor": 1180000,
      "balance_at_scheduling_minor": 1180000,
      "sent_total_minor": null,
      "sent_outstanding_minor": null,
      "sent_html_body": "",
      "approved_custom_intro": "",
      "approved_custom_closing": "",
      "needs_manual_followup": false,
      "approved_by": null,
      "approved_at": null,
      "rejected_by": null,
      "rejected_at": null,
      "dispatched_at": null,
      "block_reason": "",
      "retry_count": 0,
      "email_preview_subject": "Upcoming Payment Due: Invoice INV-2025-042",
      "email_preview_html": null,
      "created_at": "2025-07-03T05:30:00Z"
    }
  ]
}
```

#### `GET /api/v1/reminders/jobs-v2/{id}/?include_preview=true`
Retrieve one job with the full HTML email preview rendered.

#### `POST /api/v1/reminders/jobs-v2/{id}/approve/`
Approve and dispatch a reminder. Requires FINANCE_ROLES.

**Request body** (all optional):
```json
{
  "custom_intro": "Please note we have updated our banking details.",
  "custom_closing": "We look forward to hearing from you."
}
```

**Success response:**
```json
{"detail": "Reminder approved and queued for dispatch.", "job_id": "job-uuid-1"}
```

**Error responses:**
- `400` — job not in `proposed` state: `{"detail": "Job is in status 'dispatched', not 'proposed'."}`
- `400` — invoice paid: `{"detail": "Invoice has been fully paid since job was created."}`
- `400` — invoice voided: `{"detail": "Invoice has been voided."}`
- `403` — insufficient role: `{"detail": "Only Finance Manager or Business Owner can approve reminders."}`

#### `POST /api/v1/reminders/jobs-v2/{id}/reject/`
Reject a job (status `proposed` or `scheduled` only).

**Response:** `{"detail": "Reminder rejected."}`

#### `POST /api/v1/reminders/jobs-v2/{id}/mark_for_followup/`
Flag a job for manual follow-up.

**Response:** `{"detail": "Marked for manual followup."}`

---

### 6.5 Reminder Jobs (old system — `/jobs/`)

Same endpoints but under `/api/v1/reminders/jobs/` and using `ReminderJobSerializer`. Used by the old policy system. The approve endpoint calls `messaging.tasks.dispatch_reminder_job` (plain text) instead of `dispatch_reminder_email` (HTML).

---

### 6.6 Reminder Policies (old system)

#### `GET /api/v1/reminders/policies/`
#### `POST /api/v1/reminders/policies/`
#### `PUT/PATCH /api/v1/reminders/policies/{id}/`
#### `POST /api/v1/reminders/policies/{id}/activate-auto/`
#### `POST /api/v1/reminders/policies/{id}/deactivate-auto/`

---

### 6.7 Seed Defaults

#### `POST /api/v1/reminders/seed-defaults/`
Creates four default email templates and one 4-step schedule for the current org, if they don't already exist. Requires FINANCE_ROLES.

**Response:**
```json
{
  "message": "Default reminder setup created successfully",
  "schedule_id": "schedule-uuid",
  "schedule_name": "Standard Payment Reminder Workflow",
  "steps_created": 4,
  "templates_count": 4,
  "note": "All steps are set to manual approval by default. ..."
}
```

---

### 6.8 Notifications

#### `GET /api/v1/notifications/`
List the current user's most recent 50 notifications in the active org, with live-enriched details.

**Response:**
```json
{
  "unread_count": 3,
  "notifications": [
    {
      "id": "notif-uuid",
      "event_type": "reminder_approval",
      "entity_type": "reminder_job",
      "entity_id": "job-uuid",
      "payload": {
        "invoice_number": "INV-2025-042",
        "customer_name": "Acme Pvt Ltd",
        "step_label": "Step 2"
      },
      "read": false,
      "created_at": "2025-07-03T05:30:00Z",
      "details": {
        "customer_name": "Acme Pvt Ltd",
        "invoice_number": "INV-2025-042",
        "outstanding_minor": 1180000,
        "due_date": "2025-07-10",
        "days_overdue": 0,
        "step_label": "7 days before due",
        "job_status": "proposed",
        "block_reason": null
      }
    }
  ]
}
```

For `reminder_failed` notifications, `details.block_reason` will be populated.

#### `POST /api/v1/notifications/{id}/read/`
Mark one notification as read.

**Response:** `{"detail": "Marked as read."}`

#### `POST /api/v1/notifications/mark-all-read/`
Mark all unread notifications for the current user as read.

**Response:** `{"detail": "All notifications marked as read."}`

---

## 7. Configuration

### 7.1 Email environment variables

All live in `backend/.env` (never commit this file). `backend/.env.example` shows the placeholders.

| Variable | What it does | Default |
|---|---|---|
| `EMAIL_BACKEND` | Django email backend class | `django.core.mail.backends.console.EmailBackend` |
| `EMAIL_FROM` | The `From:` address on all outgoing emails | `noreply@finpilot.ai` |
| `EMAIL_HOST` | SMTP server hostname | (empty — required for SMTP backend) |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_HOST_USER` | SMTP login username | (empty) |
| `EMAIL_HOST_PASSWORD` | SMTP login password — **keep secret** | (empty) |
| `EMAIL_USE_TLS` | Use STARTTLS | `true` |

**Development:** Leave `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend`. All "sent" emails will print to the terminal instead of going to real addresses.

**Production with Gmail:**
```
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=<YOUR_GMAIL_ADDRESS>
EMAIL_HOST_PASSWORD=<16_CHAR_APP_PASSWORD>
EMAIL_USE_TLS=true
EMAIL_FROM=<YOUR_GMAIL_ADDRESS>
```
*(Use a Google App Password, not your account password.)*

**Production with SendGrid:**
```
EMAIL_HOST=smtp.sendgrid.net
EMAIL_PORT=587
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<SENDGRID_API_KEY>
```

### 7.2 Celery environment variables

| Variable | What it does | Default |
|---|---|---|
| `CELERY_BROKER_URL` | Redis URL for task queue | `redis://127.0.0.1:6379/0` |
| `CELERY_RESULT_BACKEND` | Redis URL for task results | `redis://127.0.0.1:6379/1` |
| `CELERY_TASK_ALWAYS_EAGER` | If `true`, tasks run synchronously in the web process (dev only) | `false` |

### 7.3 Django / general

| Variable | What it does | Default |
|---|---|---|
| `DJANGO_SECRET_KEY` | Session signing key — **keep secret** | Required in production |
| `DJANGO_DEBUG` | Enables debug mode and stack traces | `true` |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL connection | `finpilot / finpilot-local-only / 127.0.0.1 / 5432` |
| `EMAIL_WEBHOOK_SECRET` | HMAC secret for inbound email webhook (not currently used) | (empty) |
| `MESSAGING_WEBHOOK_SECRET` | HMAC secret for inbound messaging webhook (not currently used) | (empty) |

### 7.4 Running the full stack locally

```powershell
# 1. Start Docker services (PostgreSQL + Redis)
docker-compose up -d

# 2. Terminal 1 — Django web server (port 8000)
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py runserver

# 3. Terminal 2 — Celery worker (processes email dispatch tasks)
cd backend
.\.venv\Scripts\Activate.ps1
celery -A config worker --loglevel=info

# 4. Terminal 3 — Celery Beat scheduler (fires hourly reminder scan)
cd backend
.\.venv\Scripts\Activate.ps1
celery -A config beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler

# 5. Terminal 4 — React frontend (port 5173)
cd frontend
npm run dev
```

**Note:** `CELERY_TASK_ALWAYS_EAGER=true` in `.env` makes tasks run synchronously inside the web process, so you don't need separate worker/beat terminals in development. The `.env.example` defaults to `false`, so you need the separate workers for tasks to actually execute.

### 7.5 Registering the hourly Beat task

The `schedule_step_reminders` task must be registered in Celery Beat's database. This is done through the Django admin (`/admin/`) or by adding a row to the `django_celery_beat_periodictask` table:

```python
# Example: add via Django shell
from django_celery_beat.models import PeriodicTask, IntervalSchedule
schedule, _ = IntervalSchedule.objects.get_or_create(every=1, period=IntervalSchedule.HOURS)
PeriodicTask.objects.get_or_create(
    name="Hourly Reminder Scheduler",
    task="reminders.schedule_step_reminders",
    defaults={"interval": schedule, "enabled": True}
)
```

---

## 8. Safety Rules

### 8.1 Preventing duplicate sends

**Layer 1 — Idempotency key on ReminderJob creation:**
Every `ReminderJob` has a `UNIQUE` database constraint on `idempotency_key`.
Key format: `"{schedule_id}:{step_id}:{invoice_id}:{trigger_date}"`

Before creating a job, the scheduler checks:
```python
if ReminderJob.objects.filter(idempotency_key=idempotency_key).exists():
    continue
```
(`schedule_tasks.py` lines approx. 130–135 and 185–190)

If the hourly task runs twice in a minute (e.g., after a crash restart), the second run finds the key and skips. The database constraint catches any race condition the application check misses.

**Layer 2 — Duplicate-send check in dispatch task:**
Inside `dispatch_reminder_email`, before `send_mail` is called:
```python
already_sent = ReminderJob.objects.filter(
    schedule=schedule, step=step, invoice=inv,
    status=ReminderJob.Status.DISPATCHED,
).exclude(id=job.id).exists()
if already_sent:
    block("A reminder for this step and invoice has already been sent.")
    return
```
(`dispatch_tasks.py`, inside `dispatch_reminder_email`)

**Layer 3 — `UniqueConstraint` on ReminderJob:**
```python
models.UniqueConstraint(
    fields=["schedule", "step", "invoice"],
    name="unique_reminder_job_per_step_invoice",
    condition=Q(status__in=["proposed","approved","scheduled","dispatched"]),
)
```
(`models.py`, `ReminderJob.Meta`)

This prevents two active jobs for the same step+invoice from existing simultaneously at the database level.

---

### 8.2 Blocking reminders on paid or void invoices

**On payment allocation (before dispatch):**
```python
# signals.py — check_invoice_paid_and_cancel_reminders
if outstanding == 0:
    cancel_reminders_for_paid_invoice.delay(str(invoice.id))
```
When a payment is recorded and the balance reaches zero, all `proposed`/`approved`/`scheduled` jobs are bulk-updated to `blocked`.

**At dispatch time (final check):**
```python
# dispatch_tasks.py — dispatch_reminder_email
active_paid = sum(a.amount_minor for a in inv.allocations.filter(reversed_at__isnull=True))
outstanding = max(0, inv.total_minor - active_paid)
if outstanding == 0:
    block("Invoice balance is zero — invoice has been paid.")
    return
if inv.status == "void":
    block("Invoice has been voided.")
    return
```

**At approval time (pre-dispatch check):**
```python
# schedule_views.py — EnhancedReminderJobViewSet.approve
if balance == 0:
    job.status = ReminderJob.Status.BLOCKED
    job.block_reason = "Invoice has been fully paid since job was created."
    job.save()
    return Response({"detail": job.block_reason}, status=400)
if inv.status == "void":
    job.status = ReminderJob.Status.BLOCKED
    job.block_reason = "Invoice has been voided."
    job.save()
    return Response({"detail": job.block_reason}, status=400)
```

**Gap:** Voiding an invoice does **not** immediately cancel pending `proposed` jobs. The jobs remain `proposed` until someone tries to approve them (caught at approval) or the worker attempts to dispatch them (caught at dispatch). There is no signal on `Invoice.status` changing to `void` that cancels jobs proactively.

---

### 8.3 Cross-organization access prevention

**Permission class on every ViewSet:**
```python
permission_classes = [permissions.IsAuthenticated, HasOrganizationAccess]
```

**`HasOrganizationAccess`** (defined in `core/permissions.py`) attaches `request.membership` — the user's membership in the organization specified by `X-Organization-ID`. If the user is not a member of that organization, the request is rejected with 403.

**Every queryset is scoped to the org:**
```python
# schedule_views.py — ReminderScheduleViewSet.get_queryset
return ReminderSchedule.objects.filter(
    organization=self.request.membership.organization,
    archived=False,
)
```
A user can never retrieve or modify another organization's schedules, jobs, or notifications.

**Notifications are double-scoped:**
```python
# notifications/views.py — mark_read
Notification.objects.get(
    id=notification_id,
    recipient=request.user,
    organization=request.membership.organization,
)
```
Both the `recipient` and `organization` must match, so a user cannot mark another user's notifications as read even within the same org.

---

### 8.4 Customer opt-out

**Checked at scheduling time:**
```python
# schedule_tasks.py — schedule_step_reminders
if customer.opt_out:
    continue
```

**Checked at dispatch time:**
```python
# dispatch_tasks.py — dispatch_reminder_email
if customer.opt_out:
    block("Customer has opted out of reminders.")
    return
```

**Schedule-level exclusion list:**
```python
# schedule_tasks.py
if str(customer.id) in schedule.excluded_customer_ids:
    continue
```
(`excluded_customer_ids` is a JSON array of UUID strings stored on `ReminderSchedule`.)

---

### 8.5 Correct amounts (no stale figures)

**Snapshot at scheduling time:** The job stores `snapshot_outstanding_minor`, `snapshot_total_minor`, etc. at creation.

**Live check at dispatch time:** The dispatch task recalculates the current balance from live allocations and updates the snapshot if it has changed by more than 1 paise:
```python
# dispatch_tasks.py
if abs(outstanding - job.balance_at_scheduling_minor) > 1:
    job.balance_at_scheduling_minor = outstanding
    job.snapshot_outstanding_minor = outstanding
    job.snapshot_paid_minor = active_paid
    job.save()
```
The HTML email is then built from the **live** context, not the snapshot. The `sent_outstanding_minor` stored after a successful send is also the live amount.

**Amount display in preview:** The `EnhancedReminderJobSerializer.get_current_outstanding_minor` method re-queries the database every time the job is serialized, so the UI always shows the current balance rather than the snapshot.

---

### 8.6 Template revision safety

If a template's body or subject is changed and the template is in use by an active policy or step:
```python
# serializers.py — ReminderTemplateSerializer.update
if is_active_policy and (body_changed or subject_changed):
    ReminderTemplateRevision.objects.create(
        template=instance,
        previous_subject=instance.subject,
        previous_body=instance.body,
        changed_by=self.context["request"].user,
    )
    validated_data["pending_revision"] = True
```
The old version is preserved, and `pending_revision=True` is set on the template, flagging it for review. A finance manager must call `POST /templates/{id}/approve-revision/` to clear the flag. ⚠️ **The revision flag does not currently block sending** — it is informational only.

---

## 9. Known Limitations and Gaps

### 9.1 WhatsApp is not implemented
The `ReminderTemplate.Channel` and `ReminderJob` models have `whatsapp` values, the UI shows "WhatsApp (coming soon)", and `messaging/tasks.py` has a placeholder comment for WhatsApp. No WhatsApp provider is wired. Any job with `channel=whatsapp` will be blocked at dispatch with "Customer has no valid whatsapp contact" unless the customer has a phone number, and even then no actual message will be sent because the code only handles `channel == "email"`.

### 9.2 No email delivery confirmation (no webhooks)
`MessageLog.delivered_at` and `MessageLog.provider_message_id` exist in the schema, but no webhook handler is implemented (`messaging/views.py` is empty). The `delivered` status is never set by any code. You cannot currently tell whether an email was actually opened or delivered — only whether Django's `send_mail` returned without raising an exception.

### 9.3 No bounce handling
If an email bounces (invalid address, full mailbox), the SMTP server may return an error or bounce silently. The bounce is not captured back into the system. `customer.email` is never automatically invalidated.

### 9.4 Two parallel scheduler systems
`tasks.py` (old, policy-based) and `schedule_tasks.py` (new, schedule/step-based) both run hourly via Celery Beat if both are registered. The old system uses `messaging.tasks.dispatch_reminder_job` and the new system uses `dispatch_tasks.dispatch_reminder_email`. An organization using both will produce jobs via both paths. New setups should use only the schedule/step system.

### 9.5 `schedule_views_new.py` is dead code
`schedule_views_new.py` is a byte-for-byte duplicate of `schedule_views.py`. It is not imported anywhere. It should be deleted to avoid confusion, but this is a documentation note — it was not changed.

### 9.6 `reschedule_invoice_reminders` is not called anywhere
`schedule_tasks.py` defines `reschedule_invoice_reminders(invoice, old_schedule_id)` but no signal or view calls it. Changing an invoice's `reminder_schedule` FK does not trigger rescheduling. The function is effectively dead code or a placeholder for a future feature.

### 9.7 `NotificationPreference` is not consulted
The `NotificationPreference` table exists and has a `get_or_create`-friendly schema, but nowhere in the notification-creation code is it checked before creating notifications. All owners and managers always get every notification.

### 9.8 No rate limiting on reminder sends
There is no global rate limiter on outgoing email volume. If a large batch of invoices all share the same due date and a step fires, the system will attempt to send all of them at once. This could exceed SMTP provider per-hour limits.

### 9.9 Invoice void does not immediately cancel pending jobs
When an invoice is voided (`status=void`), no signal cancels pending `ReminderJob` records. Jobs remain `proposed` until a user tries to approve them (caught by the approval view) or the worker tries to dispatch them (caught by the dispatch task). The `cancel_reminders_for_paid_invoice` task only runs for balance-zero scenarios.

### 9.10 Signal `create_initial_invoice_email` uses `.first()` instead of `is_default`
In `signals.py`, the signal picks the first enabled schedule rather than the invoice's explicitly assigned schedule or the org's `is_default` schedule:
```python
schedule = ReminderSchedule.objects.filter(
    organization=instance.organization,
    enabled=True
).first()
```
This may assign a different schedule than the scheduler task would, depending on order. The scheduler uses `get_schedule_for_invoice()` which checks `invoice.reminder_schedule_id` first and then `is_default`. The signal bypasses both.

### 9.11 `sent_html_body` is truncated to 5000 characters
The dispatch task stores only the first 5000 characters of the HTML email body in `ReminderJob.sent_html_body`. If you need to review exactly what was sent for a long email, the full content is not stored.

### 9.12 Plan limits are checked but not enforced
`tasks.py` defines `check_plan_limits(org_id)` and it queries `Subscription` and `MessageLog`, but this function is never called by the dispatch path. There is no active enforcement of `plan.max_messages_per_month`.

---

## 10. Glossary

**Approval mode** — Whether a reminder step sends automatically or requires a human to review and click Approve. `manual` = human required; `automatic` = Celery sends it without review (requires explicit confirmation to enable).

**AuditLog** — An append-only database table in `core` that records every write operation in the system. The reminder system writes entries like `reminder_job.approved`, `reminder_job.dispatched`, `reminder_job.blocked`.

**Celery** — A Python task queue library. The Django web server places tasks (like "send this email") into a queue, and a separate Celery worker process picks them up and executes them. This keeps the web server responsive and isolates failures.

**Celery Beat** — The Celery scheduler component. It fires tasks on a schedule (like cron). FinPilot uses it to run the hourly reminder scan. Beat requires its own process (separate from the worker).

**CheckConstraint** — A PostgreSQL-level rule that rejects invalid data. In `ReminderStep`, the constraint `step_has_exactly_one_offset` ensures either `offset_from_due` or `offset_from_issue` is set, never both.

**Django signal** — A mechanism where code runs automatically when a model is saved or deleted. FinPilot uses `post_save` signals on `Invoice` and `PaymentAllocation` to trigger reminder actions without the caller needing to know about reminders.

**Exponential backoff** — A retry strategy where the wait between retries grows: 30s, 60s, 120s, 240s, 480s. It prevents hammering a failing SMTP server and gives it time to recover.

**FINANCE_ROLES** — The set of Membership roles that can approve reminders, change schedules, and perform other sensitive actions. Currently `["owner", "manager"]`.

**HasOrganizationAccess** — A Django REST Framework permission class (in `core/permissions.py`) that checks the `X-Organization-ID` header, finds the user's membership, and attaches it to `request.membership`. Requests from non-members are rejected with 403.

**HTML email** — An email whose body is HTML rather than plain text. FinPilot generates HTML emails using Python f-strings in `email_rendering.py`. The HTML is inlined (no external CSS files) for maximum email client compatibility.

**Idempotency key** — A unique string stored on `ReminderJob` that prevents the same job from being created twice. If the hourly scheduler runs twice (e.g., after a crash), the second run finds the key already exists and skips. The database enforces uniqueness.

**MessageLog** — A database record created for every email dispatch attempt. Tracks who it was sent to, when, what the subject was, whether it succeeded, and any error details. Equivalent to a postal receipt.

**Migration** — A Django file that describes a database schema change (adding a table, adding a column). Run with `python manage.py migrate`. The reminders app has 4 migrations tracking schema evolution.

**Notification** — An in-app alert stored in the database for a specific user. Not an email to the user — it appears in the UI bell icon. The `event_type` field distinguishes reminder approvals, failures, import completions, etc.

**Offset** — The number of days relative to a reference date that determines when a step fires. `offset_from_due=-7` means 7 days before the due date; `offset_from_due=3` means 3 days after; `offset_from_issue=0` means the same day the invoice is issued.

**Organisation-scoped queryset** — Every database query for sensitive data includes a `.filter(organization=...)` clause to ensure a user cannot accidentally or maliciously access another organization's data.

**Paise** — The smallest unit of Indian currency (1 INR = 100 paise). All monetary values in FinPilot are stored as integers in paise to avoid floating-point rounding errors.

**Periodic task** — A Celery task that runs on a fixed schedule (hourly, daily, etc.), managed by Celery Beat. The `schedule_step_reminders` task is a periodic task.

**prefetch_related** — A Django ORM optimization that loads related objects in a single extra query instead of one query per object. `dispatch_tasks.py` uses it to load all invoice items and payment allocations without N+1 queries.

**Redis** — An in-memory data store used as the message broker between Django and the Celery worker. When Django calls `.delay()` on a task, it pushes a message into Redis. The Celery worker polls Redis for messages and executes tasks.

**select_related** — A Django ORM optimization that uses a SQL JOIN to load related objects in the same query. Used throughout the reminder code to avoid extra database round-trips.

**Serializer** — A Django REST Framework class that converts Python objects (model instances) to JSON for API responses, and validates/converts JSON back to Python for API requests. FinPilot has two serializer layers: the old one in `serializers.py` and the new one in `schedule_serializers.py`.

**Snapshot** — The financial state (outstanding balance, total, paid, due date) of an invoice at the time a `ReminderJob` is created. Stored because the invoice may change between scheduling and dispatch. The email always uses live amounts, but the snapshot lets you audit what the state was when the job was created.

**STARTTLS** — The standard way to encrypt an SMTP connection. The connection starts unencrypted and then upgrades to TLS. Used when `EMAIL_USE_TLS=true` and `EMAIL_PORT=587`.

**ViewSet** — A Django REST Framework class that bundles multiple related API endpoints (list, create, retrieve, update, delete) into one class. `EnhancedReminderJobViewSet` is a `ReadOnlyModelViewSet` with extra custom actions (`approve`, `reject`, `mark_for_followup`).

**`transaction.atomic()`** — A Django database context manager that wraps operations in a SQL transaction. If any operation inside the block fails, all changes are rolled back. Used when creating `ReminderJob` records to ensure the job and notification are either both created or neither.

**Tone** — The register/urgency of a reminder email. Four tones: `issue` (neutral invoice notification), `friendly` (polite pre-due reminder), `gentle` (soft overdue notice), `serious` (urgent overdue demand). The tone controls the greeting, opening paragraph, and subject line.

**UUID** — A randomly generated 128-bit identifier. All primary keys in FinPilot use UUIDs rather than sequential integers, which prevents enumeration attacks.

**WhatsApp** — A messaging channel that is modelled in the codebase (`channel="whatsapp"`) but not yet implemented. All WhatsApp-related code paths are stubs or dead code.

**`X-Organization-ID` header** — A custom HTTP header the frontend sends with every API request to tell the backend which organization the user is acting on behalf of. Required by `HasOrganizationAccess`.
