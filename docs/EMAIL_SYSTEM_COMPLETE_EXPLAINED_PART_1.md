# FinPilot AI — Email & Reminder System: Complete Explanation (Part 1 of 2)

> **Coverage:** Sections 1–5 (Overview, File Structure, Full Source Code, Complete Flows, Database)
> **Part 2** covers: API Reference, Configuration, Safety Rules, Known Limitations, Glossary.
>
> This document describes **only what actually exists in the code**. Anything uncertain is explicitly flagged.

---

## 1. Overview in Plain Language

### The story, from invoice to inbox

**Step 1 — Invoice created**
A user creates an invoice for a customer and changes its status from `draft` to `issued`.
The moment that save completes, a Django signal (`post_save` on `Invoice`) fires automatically in the same web-server process.

**Step 2 — Initial email job created by signal**
The signal (`reminders/signals.py`) looks up the organization's reminder schedule. If the schedule has a Step 1 configured with `offset_from_issue=0` (meaning "send on the day the invoice is issued"), the signal creates a `ReminderJob` record in the database with status `proposed`.

**Step 3 — Notification appears in the app**
Still inside that same signal, the system creates a `Notification` record for every owner/manager in the organization. That notification has `event_type = reminder_approval` and stores the job's UUID as `entity_id`. The next time those users open the app or poll the notifications endpoint, they see a bell icon badge.

**Step 4 — Scheduler creates future reminder jobs**
Separately, a Celery Beat periodic task (`schedule_step_reminders` in `reminders/schedule_tasks.py`) runs once per hour. It scans every issued invoice in every organization, figures out which schedule applies to each invoice, then checks whether today's date matches any step's trigger date. If it does, and no job already exists for that (schedule, step, invoice, date) combination, it creates a new `ReminderJob`.

For example: if a schedule has a step saying "send 7 days before due date" and an invoice is due on 2025-07-10, the scheduler creates the job on 2025-07-03.

**Step 5 — The user reviews and approves (manual mode)**
The user opens the Reminders page in the UI, sees the job in the "Pending Approvals" tab, clicks "Preview & Approve", reads the HTML email preview (rendered live), optionally adds a custom intro or closing message, then clicks Approve.

**Step 6 — Approval API call, job dispatched to Celery**
The browser calls `POST /api/v1/reminders/jobs-v2/{id}/approve/`. The view (`EnhancedReminderJobViewSet.approve`) performs a final eligibility check (is the invoice still unpaid and not voided?), marks the job `approved`, then calls `dispatch_reminder_email.delay(job_id)` — placing the task in Redis for a Celery worker to pick up.

**Step 7 — Celery worker sends the email**
The worker runs `dispatch_reminder_email` in `reminders/dispatch_tasks.py`. It performs another round of eligibility checks (paid? voided? schedule disabled? customer opted out? no email address? already sent?), then calls `build_invoice_context` and `render_html_email_body` from `email_rendering.py` to assemble a complete HTML email with line items, payment history, and a financial summary. It calls Django's `send_mail()`, which uses the configured SMTP backend.

**Step 8 — Delivery logged, job status updated**
On success, the worker creates a `MessageLog` record with `status=sent` and updates the `ReminderJob` to `dispatched`. On failure, it retries up to 5 times with exponential backoff (30 s, 60 s, 120 s, 240 s, 480 s). After all retries fail, it sets the job to `failed` and creates a failure `Notification` for the owner/managers.

**Step 9 — Invoice paid after a reminder was queued**
When a `PaymentAllocation` is saved, another signal (`check_invoice_paid_and_cancel_reminders`) fires. If the allocation brings the invoice balance to zero, it calls the `cancel_reminders_for_paid_invoice` Celery task, which bulk-updates all `proposed`/`approved`/`scheduled` jobs for that invoice to `blocked`.

**Automatic mode (alternative path)**
If a step's `approval_mode` is `automatic` (requires explicit confirmation by an owner/manager to enable), the scheduler skips step 4 and dispatches the job directly with a countdown delay calculated to land within the schedule's business hours (`send_hour_start`–`send_hour_end`), skipping configured weekdays.

---

## 2. Complete File Structure

```
backend/
├── config/
│   ├── settings.py          Email/SMTP config, Celery broker URL, all env-var defaults
│   ├── celery.py            Celery app setup; autodiscovers schedule_tasks and dispatch_tasks
│   └── urls.py              Mounts reminders.urls and notifications.urls under /api/v1/
│
├── reminders/
│   ├── models.py            All reminder data models (see Section 3)
│   ├── signals.py           Django signals: invoice issued → create job; payment → cancel jobs
│   ├── tasks.py             OLD policy-based scheduler task (schedule_reminders) + plan limit check
│   ├── schedule_tasks.py    NEW schedule/step scheduler + cancel_reminders_for_paid_invoice
│   ├── dispatch_tasks.py    Email dispatch Celery task (HTML email, retries, audit log)
│   ├── email_rendering.py   HTML email builder: build_invoice_context, render_html_email_body
│   ├── serializers.py       OLD policy/template/job serializers + render_template helper
│   ├── schedule_serializers.py  NEW schedule/step/job serializers + ScheduleWithStepsSerializer
│   ├── views.py             OLD + NEW viewsets duplicated here (Template, Policy, Job, Schedule, Step)
│   ├── schedule_views.py    PRIMARY new ViewSets (ReminderScheduleViewSet, EnhancedReminderJobViewSet)
│   ├── schedule_views_new.py  Duplicate of schedule_views.py (unused; dead code)
│   ├── seed_api.py          POST endpoint to seed default 4-step template+schedule for an org
│   ├── urls.py              Router registrations for all reminder endpoints
│   ├── apps.py              Django app config (registers signals on ready())
│   ├── management/commands/
│   │   ├── seed_reminder_templates.py   CLI: create templates + 4-step schedule for one org
│   │   └── setup_default_schedule.py    CLI: create/update 6-step default schedule per org
│   └── migrations/
│       ├── 0001_initial.py              ReminderTemplate, ReminderPolicy, ReminderJob
│       ├── 0002_reminderdefaulttemplate.py  ReminderDefaultTemplate (read-only reference rows)
│       ├── 0003_reminderschedule_reminderstep_and_more.py  ReminderSchedule, ReminderStep
│       └── 0004_reminderschedule_is_default_archived.py   is_default, archived fields
│
├── messaging/
│   ├── models.py            MessageLog model (delivery audit trail)
│   ├── tasks.py             OLD policy-based dispatch_reminder_job task (uses plain text template)
│   ├── views.py             Empty (no webhook handler implemented)
│   ├── serializers.py       Empty
│   └── migrations/0001_initial.py
│
├── notifications/
│   ├── models.py            Notification + NotificationPreference models
│   ├── views.py             notifications_list, mark_read, mark_all_read
│   ├── urls.py              URL patterns for notification endpoints
│   ├── serializers.py       Empty
│   └── migrations/0001_initial.py
│
├── core/
│   └── models.py            Organization (timezone field), Customer (opt_out field),
│                            Invoice (reminder_schedule FK, no_reminders bool),
│                            PaymentAllocation (triggers reminder cancellation signal),
│                            AuditLog (records every reminder action)
│
frontend/
└── src/
    ├── App.tsx              RemindersPage component, ScheduleFormModal, AutoHeightIframe
    └── lib/api.ts           TypeScript types (ReminderJob, ReminderSchedule, ReminderStep,
                             ReminderTemplate, Notification, NotificationDetails, ArchiveImpact)
                             + all reminder/notification API call functions
```

---

## 3. Full Source Code, Line by Line

### 3.1 `backend/reminders/models.py`

```python
import uuid
from django.conf import settings
from django.db import models


class ReminderTemplate(models.Model):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reminder_templates"
    )
    name = models.CharField(max_length=255)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.EMAIL)
    subject = models.CharField(max_length=998, blank=True)  # email subject line
    body = models.TextField()
    active = models.BooleanField(default=True)
    # Revision control
    pending_revision = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_templates",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.channel})"


class ReminderTemplateRevision(models.Model):
    """Immutable version history for template changes."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(
        ReminderTemplate, on_delete=models.CASCADE, related_name="revisions"
    )
    previous_subject = models.CharField(max_length=998, blank=True)
    previous_body = models.TextField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="template_revisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ReminderPolicy(models.Model):
    class ApprovalMode(models.TextChoices):
        MANUAL = "manual", "Approval Required"
        AUTOMATIC = "automatic", "Automatic"

    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        WHATSAPP = "whatsapp", "WhatsApp"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reminder_policies"
    )
    name = models.CharField(max_length=255)
    applicable_statuses = models.JSONField(default=list)
    trigger_offset_days = models.IntegerField(default=0)
    channel = models.CharField(max_length=16, choices=Channel.choices, default=Channel.EMAIL)
    template = models.ForeignKey(
        ReminderTemplate, on_delete=models.PROTECT, related_name="policies",
    )
    send_hour = models.PositiveSmallIntegerField(default=9)
    send_minute = models.PositiveSmallIntegerField(default=0)
    quiet_hours_start = models.PositiveSmallIntegerField(null=True, blank=True)
    quiet_hours_end = models.PositiveSmallIntegerField(null=True, blank=True)
    max_attempts = models.PositiveSmallIntegerField(default=3)
    min_days_between_reminders = models.PositiveSmallIntegerField(default=7)
    approval_mode = models.CharField(
        max_length=16, choices=ApprovalMode.choices, default=ApprovalMode.MANUAL
    )
    auto_mode_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="confirmed_auto_policies",
    )
    excluded_customer_ids = models.JSONField(default=list)
    enabled = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_policies",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]


class ReminderDefaultTemplate(models.Model):
    """
    Shipped default templates for each tone. Read-only reference.
    Organizations copy these when creating their first policy.
    """
    class Tone(models.TextChoices):
        FRIENDLY = "friendly", "Friendly Reminder"
        FIRM = "firm", "Firm Notice"
        FINAL = "final", "Final Notice"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tone = models.CharField(max_length=16, choices=Tone.choices, unique=True)
    channel = models.CharField(max_length=16, default="email")
    subject = models.CharField(max_length=998)
    body = models.TextField()

    class Meta:
        ordering = ["tone"]


class ReminderSchedule(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reminder_schedules"
    )
    name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    archived = models.BooleanField(default=False)
    send_hour_start = models.PositiveSmallIntegerField(default=10)  # 10 AM local time
    send_hour_end = models.PositiveSmallIntegerField(default=18)    # 6 PM local time
    skip_weekdays = models.JSONField(default=list)  # 0=Monday, 6=Sunday
    excluded_customer_ids = models.JSONField(default=list)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_schedules",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class ReminderStep(models.Model):
    class Tone(models.TextChoices):
        ISSUE = "issue", "Invoice Issue Notification"
        FRIENDLY = "friendly", "Friendly Reminder"
        GENTLE = "gentle", "Gentle Reminder"
        SERIOUS = "serious", "Serious Notice"

    class ApprovalMode(models.TextChoices):
        MANUAL = "manual", "Approval Required"
        AUTOMATIC = "automatic", "Automatic"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    schedule = models.ForeignKey(
        ReminderSchedule, on_delete=models.CASCADE, related_name="steps"
    )
    step_number = models.PositiveSmallIntegerField()
    offset_from_issue = models.IntegerField(null=True, blank=True)
    offset_from_due = models.IntegerField(null=True, blank=True)
    tone = models.CharField(max_length=16, choices=Tone.choices, default=Tone.FRIENDLY)
    template = models.ForeignKey(
        ReminderTemplate, on_delete=models.PROTECT, related_name="steps"
    )
    approval_mode = models.CharField(
        max_length=16, choices=ApprovalMode.choices, default=ApprovalMode.MANUAL
    )
    auto_mode_confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="confirmed_auto_steps",
    )
    enabled = models.BooleanField(default=True)
    is_final_notice = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["step_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "step_number"],
                name="unique_step_number_per_schedule",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(offset_from_due__isnull=True, offset_from_issue__isnull=False)
                    | models.Q(offset_from_due__isnull=False, offset_from_issue__isnull=True)
                ),
                name="step_has_exactly_one_offset",
            ),
        ]


class ReminderJob(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed", "Awaiting Approval"
        APPROVED = "approved", "Approved"
        SCHEDULED = "scheduled", "Scheduled"
        DISPATCHED = "dispatched", "Dispatched"
        BLOCKED = "blocked", "Blocked"
        REJECTED = "rejected", "Rejected"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped (date passed)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "core.Organization", on_delete=models.CASCADE, related_name="reminder_jobs"
    )
    # Either policy (old system) or schedule+step (new system) will be set
    policy = models.ForeignKey(
        ReminderPolicy, on_delete=models.PROTECT, related_name="jobs", null=True, blank=True
    )
    schedule = models.ForeignKey(
        ReminderSchedule, on_delete=models.PROTECT, related_name="jobs", null=True, blank=True
    )
    step = models.ForeignKey(
        ReminderStep, on_delete=models.PROTECT, related_name="jobs", null=True, blank=True
    )
    invoice = models.ForeignKey(
        "core.Invoice", on_delete=models.PROTECT, related_name="reminder_jobs"
    )
    customer = models.ForeignKey(
        "core.Customer", on_delete=models.PROTECT, related_name="reminder_jobs"
    )
    scheduled_date = models.DateField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PROPOSED)
    # Financial snapshot at time of scheduling
    balance_at_scheduling_minor = models.BigIntegerField(default=0)
    snapshot_total_minor = models.BigIntegerField(default=0)
    snapshot_paid_minor = models.BigIntegerField(default=0)
    snapshot_outstanding_minor = models.BigIntegerField(default=0)
    snapshot_due_date = models.DateField(null=True, blank=True)
    snapshot_days_overdue = models.IntegerField(default=0)
    snapshot_created_at = models.DateTimeField(null=True, blank=True)
    # Actual amounts used when email was sent
    sent_total_minor = models.BigIntegerField(null=True, blank=True)
    sent_paid_minor = models.BigIntegerField(null=True, blank=True)
    sent_outstanding_minor = models.BigIntegerField(null=True, blank=True)
    sent_due_date = models.DateField(null=True, blank=True)
    sent_days_overdue = models.IntegerField(null=True, blank=True)
    sent_html_body = models.TextField(blank=True)   # first 5000 chars of the sent email
    # Approver customizations
    approved_custom_intro = models.TextField(blank=True)
    approved_custom_closing = models.TextField(blank=True)
    needs_manual_followup = models.BooleanField(default=False)
    idempotency_key = models.CharField(max_length=128, unique=True)
    # Approval tracking
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="approved_jobs",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="rejected_jobs",
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    block_reason = models.CharField(max_length=500, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["schedule", "step", "invoice"],
                name="unique_reminder_job_per_step_invoice",
                condition=models.Q(status__in=["proposed","approved","scheduled","dispatched"]),
            )
        ]
        ordering = ["-scheduled_date"]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "invoice"]),
            models.Index(fields=["organization", "needs_manual_followup"]),
        ]
```

#### Line-by-line explanation

**`ReminderTemplate`** — Stores the email message text that will be sent. Each organization creates its own templates. The `body` and `subject` fields use `{{placeholder}}` syntax (e.g., `{{customer_name}}`). The `pending_revision` flag is set to `True` when the body/subject of an actively-used template changes, requiring a finance manager to explicitly approve the change before it takes effect for future sends.

**`ReminderTemplateRevision`** — Immutable log. Every time an actively-used template's body or subject changes, the old version is copied here before the update is applied. This gives auditors a full edit history.

**`ReminderPolicy`** — The old reminder system (pre-schedule). Defines which invoices to target (`applicable_statuses`, `trigger_offset_days`), how often (`max_attempts`, `min_days_between_reminders`), and what to send (`template`). Still present and functional but new UIs use `ReminderSchedule`/`ReminderStep` instead.

**`ReminderDefaultTemplate`** — Read-only seeded rows (friendly, firm, final). Organizations can use these as a starting point. Not used by the dispatch system directly.

**`ReminderSchedule`** — Container for a multi-step reminder lifecycle. Defines when it is safe to send (`send_hour_start`, `send_hour_end`, `skip_weekdays`). `is_default=True` means this schedule applies to any invoice that doesn't explicitly name a different schedule. `archived=True` means the schedule is retired and hidden from the UI.

**`ReminderStep`** — One step inside a schedule. The `offset_from_issue` / `offset_from_due` fields are mutually exclusive (enforced by a database `CHECK` constraint). Negative `offset_from_due` means before the due date; positive means after. The `tone` controls the email body style. `approval_mode` can be `manual` (default, requires human approval) or `automatic` (sends without human review — requires explicit confirmation to enable).

**`ReminderJob`** — The central work-item record. Created by the scheduler or signal for each (invoice, step) pair. Tracks the full lifecycle from creation to dispatch. Stores a financial snapshot at creation time and separately stores the actual amounts used when the email was sent, so you can see if amounts changed between scheduling and sending. The `idempotency_key` ensures the same job is never created twice. Status values: `proposed` → `approved` → `dispatched` (happy path); `proposed` → `rejected` (rejected by user); any state → `blocked` (auto-blocked because invoice was paid, voided, etc.); `approved` → `failed` (email send failed permanently after retries).

---

### 3.2 `backend/reminders/signals.py`

```python
"""
Django signals for reminder automation.
Automatically creates initial invoice email jobs when invoices are issued.
"""
import logging
from datetime import date
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone

from core.models import Invoice, PaymentAllocation
from .models import ReminderJob, ReminderSchedule, ReminderStep

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Invoice)
def create_initial_invoice_email(sender, instance, created, **kwargs):
    """
    When an invoice status changes from draft to issued, automatically
    create the initial invoice email job (Step 1: Invoice Issue Notification).
    """
    if instance.status != Invoice.Status.ISSUED:
        return

    try:
        schedule = ReminderSchedule.objects.filter(
            organization=instance.organization,
            enabled=True
        ).first()

        if not schedule:
            return

        step = schedule.steps.filter(
            step_number=1,
            enabled=True,
            offset_from_issue=0
        ).first()

        if not step:
            return

        customer = instance.customer
        if str(customer.id) in schedule.excluded_customer_ids:
            return
        if customer.opt_out:
            return
        if not customer.email:
            return

        active_paid = sum(
            a.amount_minor for a in instance.allocations.filter(reversed_at__isnull=True)
        )
        outstanding = max(0, instance.total_minor - active_paid)
        if outstanding == 0:
            return

        today = date.today()
        idempotency_key = f"{schedule.id}:{step.id}:{instance.id}:{today}"

        if ReminderJob.objects.filter(idempotency_key=idempotency_key).exists():
            return

        days_overdue = max(0, (today - instance.due_date).days) if instance.due_date < today else 0

        with transaction.atomic():
            job = ReminderJob.objects.create(
                organization=instance.organization,
                schedule=schedule,
                step=step,
                invoice=instance,
                customer=customer,
                scheduled_date=today,
                balance_at_scheduling_minor=outstanding,
                snapshot_total_minor=instance.total_minor,
                snapshot_paid_minor=active_paid,
                snapshot_outstanding_minor=outstanding,
                snapshot_due_date=instance.due_date,
                snapshot_days_overdue=days_overdue,
                snapshot_created_at=timezone.now(),
                idempotency_key=idempotency_key,
                status=ReminderJob.Status.PROPOSED,
            )

            try:
                from notifications.models import Notification
                from core.models import Membership

                finance_members = Membership.objects.filter(
                    organization=instance.organization,
                    role__in=["owner", "manager"],
                    active=True,
                ).select_related("user")

                for member in finance_members:
                    Notification.objects.get_or_create(
                        organization=instance.organization,
                        recipient=member.user,
                        event_type=Notification.EventType.REMINDER_AWAITING_APPROVAL,
                        entity_type="reminder_job",
                        entity_id=str(job.id),
                        defaults={
                            "payload": {
                                "invoice_number": instance.invoice_number,
                                "customer_name": customer.name,
                                "step_label": "Initial Invoice Email",
                            }
                        },
                    )

            except Exception as e:
                logger.warning(f"Failed to create notification for initial invoice email: {e}")

    except Exception as e:
        logger.error(f"Failed to create initial invoice email for {instance.invoice_number}: {e}")


@receiver(post_save, sender=PaymentAllocation)
def check_invoice_paid_and_cancel_reminders(sender, instance, created, **kwargs):
    """
    When a payment allocation is saved and brings the invoice balance to zero,
    cancel all pending reminder jobs for that invoice.
    """
    if not created and instance.reversed_at is not None:
        return

    invoice = instance.invoice
    active_paid = sum(
        a.amount_minor for a in invoice.allocations.filter(reversed_at__isnull=True)
    )
    outstanding = max(0, invoice.total_minor - active_paid)

    if outstanding == 0:
        logger.info(f"Invoice {invoice.invoice_number} is now fully paid, cancelling pending reminders")
        try:
            from reminders.schedule_tasks import cancel_reminders_for_paid_invoice
            cancel_reminders_for_paid_invoice.delay(str(invoice.id))
        except Exception as e:
            logger.error(f"Failed to cancel reminders for paid invoice {invoice.id}: {e}")
```

#### Line-by-line explanation

**`create_initial_invoice_email`** — This function runs every time any `Invoice` is saved (because of the `@receiver(post_save, sender=Invoice)` decorator). It first checks whether the status is `issued`; if not, it returns immediately. Then it finds the first enabled `ReminderSchedule` for the organization and looks for a Step 1 with `offset_from_issue=0` (meaning "send on the day of invoice issue"). If found, it checks customer eligibility (not excluded, not opted out, has an email, invoice not already paid). Then it builds an idempotency key — `{schedule_id}:{step_id}:{invoice_id}:{today}` — and bails out if a job with that key already exists. If not, it creates the `ReminderJob` with `status=proposed` and creates `Notification` records for all owner/manager members.

**Important limitation**: This signal uses `ReminderSchedule.objects.filter(...).first()` — it picks the first enabled schedule, not necessarily the invoice's explicitly assigned schedule or the default. This is a known inconsistency with the scheduler logic. _(Flagged as uncertain whether this is intentional.)_

**`check_invoice_paid_and_cancel_reminders`** — Fires every time a `PaymentAllocation` is saved. If the new allocation brings the balance to zero, it enqueues the `cancel_reminders_for_paid_invoice` Celery task asynchronously. It skips reversed allocations (`instance.reversed_at is not None`) because a reversal brings the balance back up, not down.

---

### 3.3 `backend/reminders/schedule_tasks.py`

```python
"""
Enhanced Celery tasks for the new ReminderSchedule/ReminderStep system.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pytz
from celery import shared_task
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_schedule_for_invoice(invoice):
    """
    Returns which ReminderSchedule applies to this invoice.
    
    Resolution order:
    1. If invoice.no_reminders is True → return None
    2. If invoice.reminder_schedule is set and is enabled+not archived → use it
    3. If invoice.reminder_schedule is set but archived/disabled → fall back to org default
    4. If invoice.reminder_schedule is None → use org default
    5. No default exists → log warning, return None
    """
    from reminders.models import ReminderSchedule

    if invoice.no_reminders:
        return None

    if invoice.reminder_schedule_id:
        schedule = invoice.reminder_schedule
        if schedule.enabled and not schedule.archived:
            return schedule
        logger.info(f"Invoice {invoice.id} schedule is archived/disabled; falling back to default")

    default = ReminderSchedule.objects.filter(
        organization=invoice.organization,
        is_default=True,
        enabled=True,
        archived=False,
    ).first()

    if not default:
        logger.warning(f"No default schedule found for org {invoice.organization.id}")
        return None

    return default


def reschedule_invoice_reminders(invoice, old_schedule_id=None):
    """
    Cancel pending jobs from old_schedule_id and create new jobs from current schedule.
    Called when an invoice's schedule assignment changes.
    Only applies to issued, unpaid invoices.
    """
    from reminders.models import ReminderJob, ReminderStep
    from core.models import Invoice, Membership
    from notifications.models import Notification

    if invoice.status != Invoice.Status.ISSUED:
        return

    active_paid = sum(a.amount_minor for a in invoice.allocations.filter(reversed_at__isnull=True))
    outstanding = max(0, invoice.total_minor - active_paid)
    if outstanding == 0:
        return

    if old_schedule_id:
        ReminderJob.objects.filter(
            invoice=invoice,
            schedule_id=old_schedule_id,
            status__in=["proposed", "scheduled"],
        ).update(status=ReminderJob.Status.REJECTED, block_reason="Schedule changed on invoice")

    schedule = get_schedule_for_invoice(invoice)
    if schedule is None:
        return

    today = date.today()
    customer = invoice.customer
    org = invoice.organization
    org_tz = pytz.timezone(org.timezone)

    for step in schedule.steps.filter(enabled=True).order_by("step_number"):
        if step.offset_from_due is not None:
            trigger_date = invoice.due_date + timedelta(days=step.offset_from_due)
        else:
            trigger_date = invoice.invoice_date + timedelta(days=step.offset_from_issue)

        if trigger_date < today:
            continue  # skip past trigger dates

        if str(customer.id) in schedule.excluded_customer_ids or customer.opt_out:
            continue
        if not customer.email:
            continue

        idempotency_key = f"{schedule.id}:{step.id}:{invoice.id}:{trigger_date}"
        if ReminderJob.objects.filter(idempotency_key=idempotency_key).exists():
            continue

        days_overdue = max(0, (today - invoice.due_date).days) if invoice.due_date < today else 0

        try:
            with transaction.atomic():
                job = ReminderJob.objects.create(
                    organization=org, schedule=schedule, step=step,
                    invoice=invoice, customer=customer,
                    scheduled_date=trigger_date,
                    balance_at_scheduling_minor=outstanding,
                    snapshot_total_minor=invoice.total_minor,
                    snapshot_paid_minor=active_paid,
                    snapshot_outstanding_minor=outstanding,
                    snapshot_due_date=invoice.due_date,
                    snapshot_days_overdue=days_overdue,
                    snapshot_created_at=timezone.now(),
                    idempotency_key=idempotency_key,
                    status=(
                        ReminderJob.Status.SCHEDULED
                        if step.approval_mode == ReminderStep.ApprovalMode.AUTOMATIC
                        else ReminderJob.Status.PROPOSED
                    ),
                )
                if step.approval_mode == ReminderStep.ApprovalMode.AUTOMATIC:
                    from reminders.dispatch_tasks import dispatch_reminder_email
                    dispatch_reminder_email.apply_async(
                        args=[str(job.id)],
                        countdown=_calculate_dispatch_delay(schedule, org_tz, trigger_date),
                    )
                else:
                    finance_members = Membership.objects.filter(
                        organization=org, role__in=["owner", "manager"], active=True,
                    ).select_related("user")
                    for member in finance_members:
                        Notification.objects.get_or_create(
                            organization=org, recipient=member.user,
                            event_type=Notification.EventType.REMINDER_AWAITING_APPROVAL,
                            entity_type="reminder_job", entity_id=str(job.id),
                            defaults={
                                "payload": {
                                    "invoice_number": invoice.invoice_number,
                                    "customer_name": customer.name,
                                    "step_label": f"Step {step.step_number}",
                                }
                            },
                        )
        except Exception as e:
            logger.error(f"Failed to create reminder job for invoice {invoice.id}: {e}")


@shared_task(name="reminders.schedule_step_reminders")
def schedule_step_reminders():
    """
    Celery Beat job: runs hourly.
    For each issued invoice, resolve the applicable schedule and check if any
    step's trigger date matches today. Create a ReminderJob if so.
    """
    from reminders.models import ReminderSchedule, ReminderStep, ReminderJob
    from core.models import Invoice, Organization
    from notifications.models import Notification
    from core.models import Membership

    today = date.today()
    scheduled_count = 0
    blocked_count = 0

    orgs_with_schedules = Organization.objects.filter(
        reminder_schedules__enabled=True,
        reminder_schedules__archived=False
    ).distinct()

    for org in orgs_with_schedules:
        org_tz = pytz.timezone(org.timezone)

        issued_invoices = Invoice.objects.filter(
            organization=org, status=Invoice.Status.ISSUED,
        ).select_related("customer", "reminder_schedule").prefetch_related("allocations")

        for inv in issued_invoices:
            schedule = get_schedule_for_invoice(inv)
            if schedule is None:
                continue

            customer = inv.customer
            if str(customer.id) in schedule.excluded_customer_ids:
                continue
            if customer.opt_out:
                continue
            if not customer.email:
                continue

            active_paid = sum(a.amount_minor for a in inv.allocations.filter(reversed_at__isnull=True))
            outstanding = max(0, inv.total_minor - active_paid)
            if outstanding == 0:
                continue

            for step in schedule.steps.filter(enabled=True).order_by("step_number"):
                if step.offset_from_due is not None:
                    trigger_date = inv.due_date + timedelta(days=step.offset_from_due)
                else:
                    trigger_date = inv.invoice_date + timedelta(days=step.offset_from_issue)

                if trigger_date != today:
                    continue

                idempotency_key = f"{schedule.id}:{step.id}:{inv.id}:{today}"
                if ReminderJob.objects.filter(idempotency_key=idempotency_key).exists():
                    continue

                days_overdue = max(0, (today - inv.due_date).days) if inv.due_date < today else 0

                try:
                    with transaction.atomic():
                        job = ReminderJob.objects.create(
                            organization=org, schedule=schedule, step=step,
                            invoice=inv, customer=customer,
                            scheduled_date=today,
                            balance_at_scheduling_minor=outstanding,
                            snapshot_total_minor=inv.total_minor,
                            snapshot_paid_minor=active_paid,
                            snapshot_outstanding_minor=outstanding,
                            snapshot_due_date=inv.due_date,
                            snapshot_days_overdue=days_overdue,
                            snapshot_created_at=timezone.now(),
                            idempotency_key=idempotency_key,
                            status=(
                                ReminderJob.Status.SCHEDULED
                                if step.approval_mode == ReminderStep.ApprovalMode.AUTOMATIC
                                else ReminderJob.Status.PROPOSED
                            ),
                        )

                        if step.approval_mode == ReminderStep.ApprovalMode.AUTOMATIC:
                            from reminders.dispatch_tasks import dispatch_reminder_email
                            dispatch_reminder_email.apply_async(
                                args=[str(job.id)],
                                countdown=_calculate_dispatch_delay(schedule, org_tz, today),
                            )
                            scheduled_count += 1
                        else:
                            finance_members = Membership.objects.filter(
                                organization=org, role__in=["owner", "manager"], active=True,
                            ).select_related("user")
                            for member in finance_members:
                                Notification.objects.get_or_create(
                                    organization=org, recipient=member.user,
                                    event_type=Notification.EventType.REMINDER_AWAITING_APPROVAL,
                                    entity_type="reminder_job", entity_id=str(job.id),
                                    defaults={
                                        "payload": {
                                            "invoice_number": inv.invoice_number,
                                            "customer_name": customer.name,
                                            "step_label": f"Step {step.step_number}",
                                        }
                                    },
                                )
                            scheduled_count += 1
                except Exception as e:
                    logger.error(f"Failed to create reminder job for invoice {inv.id}: {e}")
                    blocked_count += 1

    return {"scheduled": scheduled_count, "blocked": blocked_count}


def _calculate_dispatch_delay(schedule, org_tz, target_date) -> int:
    """
    Returns seconds to wait before dispatching, so the email lands within
    business hours (send_hour_start to send_hour_end), skipping skip_weekdays.
    Returns 0 to send immediately if currently within business hours.
    """
    now = timezone.now()
    org_now = now.astimezone(org_tz)

    target_dt = org_now.replace(
        hour=schedule.send_hour_start, minute=0, second=0, microsecond=0,
    )

    if target_dt <= org_now:
        current_hour = org_now.hour
        if schedule.send_hour_start <= current_hour < schedule.send_hour_end:
            return 0  # still within business hours, send immediately
        else:
            target_dt += timedelta(days=1)

    while target_dt.weekday() in (schedule.skip_weekdays or []):
        target_dt += timedelta(days=1)

    delay_seconds = int((target_dt - org_now).total_seconds())
    return max(0, delay_seconds)


@shared_task(name="reminders.cancel_reminders_for_paid_invoice")
def cancel_reminders_for_paid_invoice(invoice_id: str):
    """
    Cancel all proposed/approved/scheduled reminder jobs for a fully-paid invoice.
    Called by the PaymentAllocation post_save signal.
    """
    from reminders.models import ReminderJob
    from core.models import Invoice

    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return

    cancelled_count = ReminderJob.objects.filter(
        invoice=invoice,
        status__in=[
            ReminderJob.Status.PROPOSED,
            ReminderJob.Status.APPROVED,
            ReminderJob.Status.SCHEDULED,
        ]
    ).update(
        status=ReminderJob.Status.BLOCKED,
        block_reason="Invoice has been fully paid"
    )

    logger.info(f"Cancelled {cancelled_count} pending reminders for invoice {invoice.invoice_number}")
    return {"cancelled": cancelled_count}


@shared_task(name="reminders.cleanup_old_reminder_jobs")
def cleanup_old_reminder_jobs(days_to_keep: int = 90):
    """
    Delete blocked/rejected/failed/skipped jobs older than days_to_keep days.
    Keeps dispatched jobs permanently.
    """
    from reminders.models import ReminderJob

    cutoff = timezone.now() - timedelta(days=days_to_keep)
    deleted = ReminderJob.objects.filter(
        status__in=[
            ReminderJob.Status.BLOCKED,
            ReminderJob.Status.REJECTED,
            ReminderJob.Status.FAILED,
            ReminderJob.Status.SKIPPED,
        ],
        created_at__lt=cutoff,
    ).delete()

    return {"deleted": deleted[0]}
```

#### Line-by-line explanation

**`get_schedule_for_invoice`** — The single authoritative function for "which schedule does this invoice use?". The resolution order is: (1) `no_reminders` flag short-circuits to None; (2) explicit schedule on invoice if enabled; (3) fallback to org's `is_default` schedule. Everything else calls this function so the logic is in one place.

**`reschedule_invoice_reminders`** — Called when an invoice's schedule assignment changes (not wired to a signal automatically — ⚠️ this function is defined but there is no signal or view that calls it; it appears to be dead code or a future hook). It cancels old pending jobs and creates new ones from future-dated steps.

**`schedule_step_reminders`** — The main hourly Celery Beat task. It queries all organizations that have at least one enabled, non-archived schedule, then for each issued invoice in each org, resolves the schedule, checks all step trigger dates, and creates jobs for today's matches. Each job is wrapped in `transaction.atomic()` so a failure on one doesn't roll back others.

**`_calculate_dispatch_delay`** — Helper that returns seconds to wait before dispatching so the email arrives within `send_hour_start`–`send_hour_end` local time. It also skips days listed in `skip_weekdays`. Returns 0 if the current time is already within business hours.

**`cancel_reminders_for_paid_invoice`** — Uses a single bulk `update()` call rather than loading and saving each job individually, which is efficient for invoices with many pending steps.

**`cleanup_old_reminder_jobs`** — Housekeeping task. Deletes terminal-state jobs older than 90 days (configurable). Dispatched jobs are never deleted by this task.

---

### 3.4 `backend/reminders/dispatch_tasks.py`

```python
"""
Email dispatch tasks with enhanced rendering including invoice details and payment history.
"""
import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings as dj_settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def dispatch_reminder_email(self, job_id: str):
    """
    Dispatch a single approved/scheduled reminder job with rich email content.
    Performs final eligibility check before sending.
    Uses exponential backoff: 30s, 60s, 120s, 240s, 480s.
    """
    from reminders.models import ReminderJob
    from reminders.email_rendering import build_invoice_context, render_html_email_body, generate_email_subject
    from messaging.models import MessageLog
    from core.models import AuditLog

    try:
        job = ReminderJob.objects.select_related(
            "schedule", "step__template", "invoice", "customer", "organization"
        ).prefetch_related("invoice__items", "invoice__allocations__payment").get(id=job_id)
    except ReminderJob.DoesNotExist:
        logger.error(f"ReminderJob {job_id} not found")
        return

    org = job.organization
    inv = job.invoice
    customer = job.customer
    step = job.step
    schedule = job.schedule

    # ── Final eligibility checks ───────────────────────────────────────────
    active_paid = sum(a.amount_minor for a in inv.allocations.filter(reversed_at__isnull=True))
    outstanding = max(0, inv.total_minor - active_paid)

    def block(reason: str):
        job.status = ReminderJob.Status.BLOCKED
        job.block_reason = reason
        job.save()
        AuditLog.objects.create(
            organization=org,
            action="reminder_job.blocked",
            entity_type="reminder_job",
            entity_id=str(job.id),
            summary=reason,
        )

    if outstanding == 0:
        block("Invoice balance is zero — invoice has been paid.")
        return
    if inv.status == "void":
        block("Invoice has been voided.")
        return
    if not schedule.enabled:
        block("Reminder schedule has been disabled.")
        return
    if not step.enabled:
        block("Reminder step has been disabled.")
        return
    if customer.opt_out:
        block("Customer has opted out of reminders.")
        return
    if not customer.email:
        block("Customer has no valid email address.")
        return

    # Duplicate-send check
    already_sent = ReminderJob.objects.filter(
        schedule=schedule, step=step, invoice=inv,
        status=ReminderJob.Status.DISPATCHED,
    ).exclude(id=job.id).exists()
    if already_sent:
        block("A reminder for this step and invoice has already been sent.")
        return

    # Update balance snapshot if invoice amount changed
    if abs(outstanding - job.balance_at_scheduling_minor) > 1:
        job.balance_at_scheduling_minor = outstanding
        job.snapshot_outstanding_minor = outstanding
        job.snapshot_paid_minor = active_paid
        job.save()

    # ── Build rich email ────────────────────────────────────────────────────
    try:
        context = build_invoice_context(inv, customer, org)
        tone = step.tone if step.tone else 'friendly'
        subject = generate_email_subject(context, tone)
        html_body = render_html_email_body(context, tone)

        if job.approved_custom_intro:
            intro_marker = "<p>This is a friendly reminder"
            if intro_marker in html_body:
                html_body = html_body.replace(intro_marker,
                    f"<p>{job.approved_custom_intro}</p><p>This is a friendly reminder", 1)

        if job.approved_custom_closing:
            closing_marker = '<p style="margin-top: 32px;">Best regards,'
            if closing_marker in html_body:
                html_body = html_body.replace(closing_marker,
                    f"<p>{job.approved_custom_closing}</p>{closing_marker}")

    except Exception as exc:
        block(f"Email rendering failed: {exc}")
        return

    # ── Create MessageLog ──────────────────────────────────────────────────
    log = MessageLog.objects.create(
        organization=org, reminder_job=job, invoice=inv, customer=customer,
        channel="email", provider="email",
        recipient=customer.email,
        subject=subject[:998],
        body_preview=context['outstanding_amount'] + " outstanding",
        status=MessageLog.Status.QUEUED,
    )

    # ── Send ───────────────────────────────────────────────────────────────
    try:
        from django.core.mail import send_mail
        send_mail(
            subject=subject,
            message="",           # empty plain-text fallback
            from_email=dj_settings.EMAIL_FROM,
            recipient_list=[customer.email],
            html_message=html_body,
            fail_silently=False,
        )

        log.status = MessageLog.Status.SENT
        log.sent_at = timezone.now()
        log.save()

        job.status = ReminderJob.Status.DISPATCHED
        job.dispatched_at = timezone.now()
        job.sent_total_minor = inv.total_minor
        job.sent_paid_minor = active_paid
        job.sent_outstanding_minor = outstanding
        job.sent_due_date = inv.due_date
        job.sent_days_overdue = context['days_overdue']
        job.sent_html_body = html_body[:5000]
        job.save()

        AuditLog.objects.create(
            organization=org,
            action="reminder_job.dispatched",
            entity_type="reminder_job",
            entity_id=str(job.id),
            summary=f"Dispatched email reminder for invoice {inv.invoice_number} "
                    f"(₹{outstanding/100:,.2f} outstanding)",
        )

    except Exception as exc:
        log.error_detail = str(exc)[:500]
        retry_delay = 30 * (2 ** self.request.retries)

        if self.request.retries < self.max_retries:
            log.retry_count = self.request.retries + 1
            log.status = MessageLog.Status.QUEUED
            log.save()
            job.retry_count += 1
            job.save()
            raise self.retry(exc=exc, countdown=min(retry_delay, 1800))
        else:
            log.status = MessageLog.Status.FAILED
            log.save()
            job.status = ReminderJob.Status.FAILED
            job.save()

            # Notify owners/managers of the failure
            try:
                from notifications.models import Notification
                from core.models import Membership
                for m in Membership.objects.filter(
                    organization=org, role__in=["owner", "manager"], active=True,
                ).select_related("user"):
                    Notification.objects.get_or_create(
                        organization=org, recipient=m.user,
                        event_type=Notification.EventType.REMINDER_FAILED,
                        entity_type="reminder_job", entity_id=str(job.id),
                        defaults={
                            "payload": {
                                "invoice_number": inv.invoice_number,
                                "customer_name": customer.name,
                                "block_reason": "Email delivery failed after retries",
                            }
                        },
                    )
            except Exception:
                pass
```

#### Line-by-line explanation

**`dispatch_reminder_email`** — The main email-sending task. Decorated with `bind=True` (gives access to `self` for retry state) and `max_retries=5`. It runs inside the Celery worker process, completely separate from the web server.

The first section loads the full job record with all related data in one database query (using `select_related` and `prefetch_related`) to avoid N+1 queries later.

The **eligibility block** runs a fresh set of checks immediately before sending. These are the same conceptual checks as at scheduling time, but with live data, since time has passed and the invoice might have been paid, voided, or the schedule disabled in the interim. The inner `block()` helper writes the reason to the job record and creates an audit log entry.

The **duplicate-send check** looks for another `ReminderJob` with the same `schedule`, `step`, and `invoice` that is already `dispatched`. This is the last line of defense against sending the same step twice (the idempotency key on job creation is the first defense).

The **balance reconciliation** step — if the invoice's current outstanding balance differs from the snapshot by more than 1 paise (the `> 1` tolerance avoids float noise), the snapshot is updated before the email is built. This means the email always shows the most current amount.

The **email building** calls `build_invoice_context`, `generate_email_subject`, and `render_html_email_body` from `email_rendering.py`. Custom intro/closing injections use string replacement on specific HTML markers.

The **retry logic** uses `self.request.retries` to calculate exponential backoff: `30 * (2 ** retries)` → 30s, 60s, 120s, 240s, 480s, capped at 1800s. `raise self.retry(...)` re-enqueues the task. After the 5th failure, the job moves to `failed` and a failure notification is created.

---

### 3.5 `backend/reminders/email_rendering.py`

```python
"""
Enhanced email rendering for payment reminders.
"""
from datetime import date
from typing import Dict, Any, List, Tuple
from decimal import Decimal
from core.formatting import fmt_qty


def money_display(paise: int) -> str:
    """Convert paise to rupees display: ₹X,XXX.XX"""
    return f"₹{paise / 100:,.2f}"


def build_invoice_context(invoice, customer, organization) -> Dict[str, Any]:
    """
    Build the data dictionary used by render_html_email_body.
    Includes: customer details, invoice header, line items, payment history,
    financial summary, overdue calculation, and business contact info.
    """
    from core.models import PaymentAllocation

    active_allocations = invoice.allocations.filter(reversed_at__isnull=True).select_related('payment')
    total_paid_minor = sum(a.amount_minor for a in active_allocations)
    outstanding_minor = max(0, invoice.total_minor - total_paid_minor)

    today = date.today()
    days_overdue = max(0, (today - invoice.due_date).days) if invoice.due_date < today else 0
    days_until_due = (invoice.due_date - today).days if invoice.due_date >= today else 0

    line_items = []
    for item in invoice.items.all().order_by('sort_order'):
        line_items.append({
            'description': item.description,
            'quantity': fmt_qty(item.quantity),
            'unit_price': money_display(item.unit_price_minor),
            'line_total': money_display(item.line_total_minor),
            'gst_rate_bps': item.gst_rate_bps,
            'gst_tax': money_display(item.gst_tax_minor) if item.gst_tax_minor > 0 else None,
        })

    payment_transactions = []
    for alloc in active_allocations.order_by('payment__payment_date'):
        payment = alloc.payment
        payment_transactions.append({
            'date': str(payment.payment_date),
            'amount': money_display(alloc.amount_minor),
            'method': payment.get_method_display(),
            'reference': payment.reference or '—',
        })

    return {
        'customer_name': customer.name,
        'customer_email': customer.email,
        'customer_contact': customer.contact_name or customer.name,
        'invoice_number': invoice.invoice_number,
        'invoice_date': str(invoice.invoice_date),
        'due_date': str(invoice.due_date),
        'days_overdue': days_overdue,
        'days_until_due': days_until_due,
        'overdue_status': 'overdue' if days_overdue > 0 else 'due_soon' if days_until_due <= 7 else 'not_due',
        'subtotal': money_display(invoice.subtotal_minor),
        'discount': money_display(invoice.discount_minor) if invoice.discount_minor > 0 else None,
        'tax': money_display(invoice.tax_minor),
        'total_amount': money_display(invoice.total_minor),
        'total_paid': money_display(total_paid_minor),
        'outstanding_amount': money_display(outstanding_minor),
        'payment_percentage': int((total_paid_minor / invoice.total_minor * 100)) if invoice.total_minor > 0 else 0,
        'total_minor': invoice.total_minor,
        'paid_minor': total_paid_minor,
        'outstanding_minor': outstanding_minor,
        'line_items': line_items,
        'line_items_count': len(line_items),
        'payment_transactions': payment_transactions,
        'payment_transactions_count': len(payment_transactions),
        'business_name': organization.name,
        'business_email': organization.business_email or 'noreply@finpilot.ai',
        'business_contact': organization.contact_phone or '',
        'business_address': organization.billing_address or '',
        'payment_reference_instructions': f"Please reference invoice {invoice.invoice_number} when making payment",
    }


def render_html_email_body(context: Dict[str, Any], tone: str = 'friendly') -> str:
    """
    Builds and returns a complete HTML email string.
    tone options: 'issue', 'friendly', 'gentle', 'serious'
    
    Structure:
    - Header: business name + "Payment Reminder"
    - Greeting + opening paragraph (tone-dependent)
    - Invoice Items table (if any)
    - Payment Summary box
    - Payment History table (if any)
    - Closing paragraph (tone-dependent)
    - Footer: business address + contact
    """
    # ... (full implementation in source; uses f-strings to build HTML tables)


def generate_email_subject(context: Dict[str, Any], tone: str = 'friendly') -> str:
    """
    Returns the email subject line based on tone and invoice state.
    
    issue   → "Invoice {number} from {business}"
    friendly (not yet overdue) → "Upcoming Payment Due: Invoice {number}"
    friendly (overdue) → "Payment Reminder: Invoice {number} (Due {date})"
    gentle  → "Payment Overdue: Invoice {number} ({days} days)"
    serious → "URGENT: Payment Required - Invoice {number}"
    """
```

#### Line-by-line explanation

**`money_display`** — Converts raw paise (integers) to formatted rupee strings. Called many times when building the context dictionary.

**`build_invoice_context`** — The data-gathering function. It queries the invoice's line items and payment allocations (filtering out reversed allocations), calculates overdue days, and assembles a plain Python dictionary. This dictionary is the single data source for both the subject line and the HTML body. The function does NOT render any HTML — it only collects data.

**`render_html_email_body`** — The HTML builder. It uses Python f-strings to assemble the HTML directly (there are no Django template files). The structure is:
- A tone-specific greeting and opening paragraph
- A table of invoice line items (with GST rates shown as subdued notes)
- A payment summary box (subtotal → discount → tax → total → amount paid → outstanding balance)
- A payment history table (only shown if partial payments exist)
- A tone-specific closing

The outstanding balance is highlighted in red if the invoice is overdue, green if on time.

**`generate_email_subject`** — Picks the subject line based on the tone and whether the invoice is overdue. The `serious` tone always starts with `URGENT:`.

---

### 3.6 `backend/reminders/serializers.py` (selected key parts)

```python
SUPPORTED_PLACEHOLDERS = {
    "customer_name", "invoice_number", "invoice_date", "due_date",
    "outstanding_amount", "payment_reference_instructions", "business_contact",
}

CHANNEL_LIMITS = {
    "email": {"subject": 998, "body": 100_000},
    "whatsapp": {"subject": 0, "body": 4096},
}

PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def validate_placeholders(subject: str, body: str, channel: str) -> list[str]:
    """Checks for oversized fields and unsupported placeholders. Returns error strings."""
    ...

def render_template(subject: str, body: str, context: dict) -> tuple[str, str]:
    """
    Used by the OLD policy-based dispatch (messaging/tasks.py).
    Substitutes {{key}} placeholders with values from context.
    HTML-escapes values to prevent injection in emails.
    Raises ValueError if a placeholder has no value in context.
    """
    ...
```

#### Line-by-line explanation

**`SUPPORTED_PLACEHOLDERS`** — The whitelist of variable names that can appear in templates. Any `{{other_name}}` in a template body or subject causes a validation error at save time.

**`validate_placeholders`** — Called by `ReminderTemplateSerializer.validate()` before saving a template. Checks both maximum length and that every `{{token}}` in the text is in the whitelist.

**`render_template`** — Used only by the **old** `messaging/tasks.py` dispatch path (policy-based). The new `dispatch_tasks.py` bypasses this and uses `email_rendering.py` to build the full HTML email instead. The function HTML-escapes each substituted value using string replacement (`&`, `<`, `>`) to prevent injection.

---

### 3.7 `backend/reminders/schedule_serializers.py` (key classes)

**`ReminderStepSerializer`** — Validates that exactly one of `offset_from_issue` / `offset_from_due` is provided. Exposes human-readable display fields for tone and approval mode.

**`ReminderScheduleSerializer`** — Read-only for `is_default`, `archived`. Embeds the active step list in the response via `get_steps()`. Automatically sets `organization` and `created_by` from the request context on create.

**`ScheduleWithStepsSerializer`** — The complex serializer that creates or updates a full schedule with its steps in one request. The UI sends steps in a human-friendly format (`{basis, kind, days, template}`), and this serializer converts them to database fields (`offset_from_issue` / `offset_from_due`). Key behaviors:
- Validates that no two steps have identical timing
- Derives tone automatically from timing (`issue` for issue-date steps, `friendly`/`gentle`/`serious` for due-date steps based on days)
- On update: steps whose timing matches an existing step reuse the existing DB row (preserving FKs from `ReminderJob` records); removed steps that have live jobs are disabled rather than deleted

**`EnhancedReminderJobSerializer`** — Serializes `ReminderJob` with computed fields including `current_outstanding_minor` (live balance from DB) and `email_preview_html` (only computed if `?include_preview=true` is in the query string, to avoid N+1 email renders when listing many jobs).

**`ReminderJobApprovalSerializer`** — Simple serializer for the approval request body: `custom_intro` and `custom_closing`, both optional, max 2000 chars.

---

### 3.8 `backend/reminders/schedule_views.py`

This file contains the **primary** (currently-routed) versions of the ViewSets. `views.py` also contains copies of `ReminderScheduleViewSet` and related classes, but `urls.py` imports from `schedule_views.py`.

**`ReminderScheduleViewSet`** — Full CRUD minus hard delete. Notable custom actions:
- `create_with_steps` / `update_with_steps` — atomic schedule+step creation via `ScheduleWithStepsSerializer`
- `toggle` — activate/deactivate; blocks deactivating the default schedule
- `archive_impact` — returns impact numbers (live jobs, affected invoices) before the user confirms an archive
- `archive` — soft-delete (sets `archived=True`, `enabled=False`); blocked if schedule is the default
- `set_default` — sets `is_default=True` and clears `is_default` on all other schedules for the org

**`ReminderStepViewSet`** — Full CRUD. Custom actions:
- `activate_auto` — sets `approval_mode=automatic`; requires `{"confirm": true}` in request body
- `deactivate_auto` — reverts to manual

**`EnhancedReminderJobViewSet`** — Read-only list/retrieve plus:
- `approve` — validates eligibility, sets `approved`, attaches custom messages, dispatches
- `reject` — sets `rejected`
- `mark_for_followup` — sets `needs_manual_followup=True`

---

### 3.9 `backend/messaging/models.py`

```python
class MessageLog(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        SENT = "sent"
        DELIVERED = "delivered"
        FAILED = "failed"
        CANCELLED = "cancelled"
        UNKNOWN = "unknown"

    id = models.UUIDField(primary_key=True, ...)
    organization = ForeignKey → Organization
    reminder_job = ForeignKey → ReminderJob (nullable)
    invoice = ForeignKey → Invoice (nullable)
    customer = ForeignKey → Customer (nullable)
    channel = CharField (email / whatsapp)
    provider = CharField (e.g. "email")
    provider_message_id = CharField (blank; for future webhook matching)
    recipient = CharField (email address or phone)
    subject = CharField (max 998 chars)
    body_preview = CharField (max 200 chars; truncated for logs)
    status = CharField (queued / sent / delivered / failed / cancelled / unknown)
    error_code = CharField (blank)
    error_detail = CharField (max 500 chars)
    retry_count = PositiveSmallIntegerField
    approved_by = ForeignKey → User (nullable)
    approved_at = DateTimeField (nullable)
    queued_at = DateTimeField (auto_now_add)
    sent_at = DateTimeField (nullable)
    delivered_at = DateTimeField (nullable)
```

#### Line-by-line explanation

**`MessageLog`** — The delivery audit record. Created with `status=queued` before the send attempt, updated to `sent` on success or `failed` after all retries. The `provider_message_id` field is blank in all current code — it was designed for webhook-based delivery confirmations (e.g., Mailgun's message ID) but no webhook handler is implemented. The `delivered` status is therefore never set by current code.

---

### 3.10 `backend/messaging/tasks.py`

This is the **old** dispatch task, used only when a job has a `policy` (not a `schedule`/`step`). It is functionally equivalent to `dispatch_tasks.py` but uses the simpler `render_template` function and sends plain-text email instead of HTML. Both tasks coexist; the new schedule/step system only ever calls `dispatch_reminder_email` from `dispatch_tasks.py`.

---

### 3.11 `backend/notifications/models.py`

```python
class Notification(models.Model):
    class EventType(models.TextChoices):
        REMINDER_AWAITING_APPROVAL = "reminder_approval", "Reminder Awaiting Approval"
        REMINDER_FAILED = "reminder_failed", "Reminder Delivery Failed"
        IMPORT_COMPLETE = "import_complete", ...
        IMPORT_FAILED = "import_failed", ...
        RECONCILIATION_REVIEW = "reconciliation_review", ...
        FORECAST_FAILED = "forecast_failed", ...
        SUBSCRIPTION_CHANGED = "subscription_changed", ...
        SECURITY_EVENT = "security_event", ...
        MEMBERSHIP_CHANGED = "membership_changed", ...
        PAYMENT_GATEWAY_EVENT = "payment_gateway", ...

    id = UUIDField (PK)
    organization = ForeignKey → Organization (nullable)
    recipient = ForeignKey → User
    event_type = CharField
    entity_type = CharField (e.g. "reminder_job")
    entity_id = CharField (UUID of the linked record)
    payload = JSONField (supplementary data, no financial amounts)
    read_at = DateTimeField (null = unread)
    created_at = DateTimeField (auto_now_add)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["organization", "recipient", "event_type", "entity_type", "entity_id"],
                name="unique_unread_notification",
                condition=Q(read_at__isnull=True),
            )
        ]
```

#### Line-by-line explanation

**`Notification`** — Represents one in-app alert for one user. The `entity_id` lets the UI look up the linked record (e.g., the `ReminderJob`) without storing redundant data in the notification itself.

The `unique_unread_notification` constraint prevents duplicate unread notifications for the same event and entity per user. This is why the code uses `Notification.objects.get_or_create(...)` — if the notification already exists and is unread, the create is silently skipped.

The `payload` field stores a small JSON dict for quick display (e.g., `{invoice_number, customer_name, step_label}`) without needing to join to other tables. Financial amounts are deliberately not stored here.

**`NotificationPreference`** — Per-user, per-org opt-in/out table. Currently not used anywhere in the notification creation code — it exists as a schema but is not consulted before creating notifications.

---

### 3.12 `backend/notifications/views.py`

**`notifications_list`** — Returns the latest 50 notifications for the current user in the current org, plus the total unread count. For each notification, calls `_enrich_notification(n)` to load live data from the linked entity (the `ReminderJob`, `ImportBatch`, or reconciliation counts). If enrichment fails (entity deleted, permissions changed), it returns `{"error": "details_unavailable"}` instead of raising an exception.

**`mark_read`** — Sets `read_at` to now on a single notification. Org-scoped (you can only mark your own org's notifications).

**`mark_all_read`** — Bulk update: sets `read_at=now()` for all unread notifications of the current user in the current org.

---

### 3.13 `backend/reminders/tasks.py` (old policy-based scheduler)

The `schedule_reminders` task is the original scheduler built around `ReminderPolicy`. It:
- Runs hourly via Celery Beat
- Finds enabled policies and eligible invoices
- Applies frequency limits (`max_attempts`, `min_days_between_reminders`)
- Creates `ReminderJob` with `idempotency_key = f"{policy_id}:{invoice_id}:{today}"`
- In automatic mode, dispatches via `messaging.tasks.dispatch_reminder_job`
- In manual mode, creates approval notifications

This system is still active but new setups use the schedule/step system in `schedule_tasks.py` instead.

---

## 4. Complete Flow, Step by Step

### 4.1 Scheduler creating reminder jobs from schedules and steps

**Trigger:** Celery Beat fires `schedule_step_reminders` once per hour.

```
Celery Beat (hourly)
  │
  └─► schedule_step_reminders()          [reminders/schedule_tasks.py]
        │
        ├─ Query: Organizations with enabled+non-archived schedules
        │
        └─► For each org:
              │
              ├─ Query: All issued invoices for this org
              │
              └─► For each invoice:
                    │
                    ├─ get_schedule_for_invoice(inv)
                    │   → Returns ReminderSchedule or None
                    │
                    ├─ Check: customer excluded? opted_out? no email? balance == 0?
                    │   → Skip if any true
                    │
                    └─► For each enabled step in schedule:
                          │
                          ├─ Calculate trigger_date
                          │   offset_from_due → invoice.due_date + days
                          │   offset_from_issue → invoice.invoice_date + days
                          │
                          ├─ if trigger_date != today → continue
                          │
                          ├─ Build idempotency_key =
                          │     "{schedule_id}:{step_id}:{invoice_id}:{today}"
                          │
                          ├─ if job with key exists → continue (idempotent)
                          │
                          ├─ transaction.atomic():
                          │     ReminderJob.objects.create(
                          │       status = SCHEDULED (auto) or PROPOSED (manual)
                          │     )
                          │
                          └─► if approval_mode == AUTOMATIC:
                                dispatch_reminder_email.apply_async(
                                  args=[job.id],
                                  countdown=_calculate_dispatch_delay(...)
                                )
                              else:
                                Notification.objects.get_or_create(
                                  event_type=REMINDER_AWAITING_APPROVAL
                                ) for each owner/manager
```

---

### 4.2 Notification creation and click-through

**Two entry points:** (a) the `create_initial_invoice_email` signal when an invoice is issued, and (b) `schedule_step_reminders` when a step fires.

```
[Invoice saved with status=issued]
  │
  └─► create_initial_invoice_email (signal)   [reminders/signals.py]
        │
        ├─ Find first enabled ReminderSchedule for org
        ├─ Find Step 1 with offset_from_issue=0
        ├─ Check eligibility
        ├─ Build idempotency_key
        └─ ReminderJob.objects.create(status=PROPOSED)
              │
              └─► For each owner/manager:
                    Notification.objects.get_or_create(
                      event_type="reminder_approval",
                      entity_type="reminder_job",
                      entity_id=str(job.id)
                    )

[User opens app]
  │
  └─► GET /api/v1/notifications/            [notifications/views.py → notifications_list]
        │
        ├─ Filter: recipient=user, organization=org
        ├─ unread_count = count(read_at__isnull=True)
        ├─ For each notification:
        │     _enrich_notification(n)
        │       → For reminder_approval: loads ReminderJob, returns
        │         {customer_name, invoice_number, outstanding_minor, step_label, ...}
        │
        └─► Return {unread_count, notifications: [...]}

[User clicks notification in UI]
  │
  └─► Frontend: navigates to Reminders page, pending tab
        │
  └─► POST /api/v1/notifications/{id}/read/    marks notification read
```

---

### 4.3 Reminder approval and sending

```
[User in Reminders page → Pending Approvals tab]
  │
  └─► GET /api/v1/reminders/jobs-v2/?status=proposed
        → EnhancedReminderJobViewSet.list()   [schedule_views.py]
        → Returns list with snapshot amounts and step info
  │
  └─► User clicks "Preview & Approve" on a job
        │
  └─► GET /api/v1/reminders/jobs-v2/{id}/?include_preview=true
        → EnhancedReminderJobViewSet.retrieve()
        → EnhancedReminderJobSerializer.get_email_preview_html()
              → build_invoice_context(invoice, customer, org)
              → render_html_email_body(context, tone)
        → Returns full job + email_preview_html

  [UI shows modal with rendered HTML email in iframe]
  User optionally edits custom_intro and custom_closing
  User clicks "Approve"
  │
  └─► POST /api/v1/reminders/jobs-v2/{id}/approve/
        body: { custom_intro: "...", custom_closing: "..." }
        │
        ├─ Permission check: role in [owner, manager]
        ├─ Check: job.status == proposed
        ├─ Eligibility check: balance > 0, not voided
        ├─ transaction.atomic():
        │     job.status = APPROVED
        │     job.approved_by = request.user
        │     job.approved_at = now()
        │     job.approved_custom_intro = custom_intro
        │     job.approved_custom_closing = custom_closing
        │     job.save()
        │     AuditLog.create(action="reminder_job.approved")
        │
        └─► dispatch_reminder_email.delay(job.id)
              → Sends task to Redis queue
              → Celery worker picks it up

  [Celery worker executes dispatch_reminder_email]
  │
  ├─ Load job with all related data
  ├─ Eligibility checks (paid? voided? schedule disabled? opted out? no email?)
  ├─ Duplicate-send check
  ├─ build_invoice_context(inv, customer, org)
  ├─ generate_email_subject(context, tone)
  ├─ render_html_email_body(context, tone)
  ├─ Apply custom intro/closing injections
  ├─ MessageLog.create(status=QUEUED)
  │
  └─► send_mail(subject, html_message, from=EMAIL_FROM, to=[customer.email])
        [Django → SMTP backend → email provider]
        │
        ├─ Success:
        │     log.status = SENT; log.sent_at = now()
        │     job.status = DISPATCHED; job.dispatched_at = now()
        │     job.sent_* fields = live amounts
        │     job.sent_html_body = html[:5000]
        │     AuditLog.create(action="reminder_job.dispatched")
        │
        └─ Failure:
              log.error_detail = str(exc)[:500]
              raise self.retry(countdown=30 * 2^retries)
```

---

### 4.4 Retry and failure handling

```
[send_mail raises Exception]
  │
  ├─ self.request.retries < 5:
  │     log.retry_count += 1; log.status = QUEUED
  │     job.retry_count += 1
  │     raise self.retry(exc=exc, countdown=min(30 * 2^retries, 1800))
  │     → Celery re-queues the task
  │
  └─ self.request.retries == 5 (max retries exhausted):
        log.status = FAILED
        job.status = FAILED
        For each owner/manager:
          Notification.objects.get_or_create(event_type=REMINDER_FAILED)

Retry schedule (seconds): 30 → 60 → 120 → 240 → 480 (capped at 1800)
```

---

### 4.5 Delivery log and history

```
[User views Sent History tab]
  │
  └─► GET /api/v1/reminders/jobs-v2/?status=dispatched
        → Returns jobs with dispatched_at, sent_outstanding_minor, step info

[User views Failed Deliveries tab]
  │
  └─► GET /api/v1/reminders/jobs-v2/?status=failed
        → Returns jobs with block_reason, retry_count

[Delivery audit at record level]
  Every dispatch attempt:
    MessageLog created → updated to sent/failed
    AuditLog entry created with action "reminder_job.dispatched" or "reminder_job.blocked"
```

---

### 4.6 Invoice paid or voided after a reminder was queued

```
[User records a payment against an invoice]
  │
  └─► PaymentAllocation saved → post_save signal fires
        → check_invoice_paid_and_cancel_reminders()   [signals.py]
              │
              ├─ Recalculate outstanding balance (excluding reversed allocations)
              │
              └─ if outstanding == 0:
                    cancel_reminders_for_paid_invoice.delay(invoice.id)
                      → Celery task (or synchronously if TASK_ALWAYS_EAGER)
                      → ReminderJob bulk update:
                           status → BLOCKED
                           block_reason → "Invoice has been fully paid"
                      for status in [proposed, approved, scheduled]

[Invoice is voided]
  No signal fires. Instead, the check happens inside dispatch_reminder_email
  when the worker runs:
    if inv.status == "void":
        block("Invoice has been voided.")
        return
  → The job is blocked at dispatch time, not before.
  ⚠️ This means a voided invoice's pending proposed/approved jobs remain in
     "proposed" state until the worker attempts to dispatch them.
```

---

## 5. Database

### Tables and their purpose

| Table | App | Purpose |
|---|---|---|
| `reminders_remindertemplate` | reminders | Email message templates with placeholder syntax |
| `reminders_remindertemplaterevision` | reminders | Immutable edit history for templates |
| `reminders_reminderpolicy` | reminders | Old trigger-offset-based policy rules |
| `reminders_reminderdefaulttemplate` | reminders | Seeded read-only reference templates |
| `reminders_reminderschedule` | reminders | Multi-step schedule container per org |
| `reminders_reminderstep` | reminders | One step in a schedule (timing + template + tone) |
| `reminders_reminderjob` | reminders | Work item for one (invoice, step) pair |
| `messaging_messagelog` | messaging | Delivery audit record for each send attempt |
| `notifications_notification` | notifications | In-app alerts for users |
| `notifications_notificationpreference` | notifications | Per-user event opt-out (not currently used) |

---

### Key field relationships

```
Organization
  ├─── ReminderSchedule (many)       ← FK: organization
  │       └─── ReminderStep (many)   ← FK: schedule
  │                └─── ReminderTemplate  ← FK: template
  │
  ├─── ReminderPolicy (many)         ← FK: organization
  │       └─── ReminderTemplate      ← FK: template
  │
  ├─── ReminderJob (many)
  │       ├─── ReminderSchedule (optional FK: schedule)
  │       ├─── ReminderStep (optional FK: step)
  │       ├─── ReminderPolicy (optional FK: policy)
  │       ├─── Invoice               ← FK: invoice
  │       └─── Customer              ← FK: customer
  │
  └─── MessageLog (many)
           └─── ReminderJob          ← FK: reminder_job

Invoice
  ├─── ReminderSchedule (optional FK: reminder_schedule)  ← per-invoice override
  └─── no_reminders (bool)           ← full opt-out for this invoice

Customer
  └─── opt_out (bool)                ← full opt-out for this customer
```

---

### Data stored at each lifecycle event

**When a ReminderJob is created:**
```
organization, schedule, step, invoice, customer
scheduled_date = today (or future trigger date)
status = "proposed" or "scheduled"
balance_at_scheduling_minor = live outstanding at creation time
snapshot_total_minor, snapshot_paid_minor, snapshot_outstanding_minor
snapshot_due_date, snapshot_days_overdue, snapshot_created_at
idempotency_key = "{schedule_id}:{step_id}:{invoice_id}:{trigger_date}"
retry_count = 0
```

**When a ReminderJob is approved:**
```
status = "approved"
approved_by = User FK
approved_at = datetime
approved_custom_intro = text (may be empty)
approved_custom_closing = text (may be empty)
```

**When a ReminderJob is dispatched (sent):**
```
status = "dispatched"
dispatched_at = datetime
sent_total_minor = live total at send time
sent_paid_minor = live paid amount at send time
sent_outstanding_minor = live outstanding at send time
sent_due_date = invoice due date at send time
sent_days_overdue = calculated days overdue at send time
sent_html_body = first 5000 chars of HTML email
```

**When a MessageLog is created (before send):**
```
organization, reminder_job, invoice, customer
channel = "email"
provider = "email"
recipient = customer.email
subject = rendered subject (max 998 chars)
body_preview = "₹X,XXX.XX outstanding" (max 200 chars)
status = "queued"
queued_at = now()
```

**When a MessageLog is updated (after successful send):**
```
status = "sent"
sent_at = now()
```

**When a ReminderJob fails:**
```
status = "failed"  (on ReminderJob)
status = "failed"  (on MessageLog)
error_detail = str(exception)[:500]  (on MessageLog)
```

**When a ReminderJob is blocked:**
```
status = "blocked"
block_reason = human-readable string (max 500 chars)
```
