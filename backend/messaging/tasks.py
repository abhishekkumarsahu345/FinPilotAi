"""
Messaging delivery tasks.
The actual email send uses Django's email backend (console in dev, SMTP/SES in prod).
"""
from celery import shared_task
from django.utils import timezone


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def dispatch_reminder_job(self, job_id: str):
    """
    Dispatch a single approved/scheduled reminder job.
    Performs final eligibility check before sending.
    Uses exponential backoff: 30s, 60s, 120s, 240s, 480s.
    """
    from reminders.models import ReminderJob
    from messaging.models import MessageLog
    from core.models import AuditLog

    try:
        job = ReminderJob.objects.select_related(
            "policy__template", "invoice", "customer", "organization"
        ).prefetch_related("invoice__allocations").get(id=job_id)
    except ReminderJob.DoesNotExist:
        return

    org = job.organization
    inv = job.invoice
    customer = job.customer
    policy = job.policy

    # ── Final eligibility checks ───────────────────────────────────────────
    active_paid = sum(
        a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
    )
    balance = max(0, inv.total_minor - active_paid)

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

    if balance == 0:
        block("Invoice balance is zero — invoice has been paid.")
        return
    if inv.status == "void":
        block("Invoice has been voided.")
        return
    if not policy.enabled:
        block("Reminder policy has been disabled.")
        return
    if customer.opt_out:
        block("Customer has opted out of reminders.")
        return
    channel = policy.channel
    recipient = customer.email if channel == "email" else customer.phone
    if not recipient:
        block(f"Customer has no valid {channel} contact.")
        return

    # Check for duplicate send
    already_sent = ReminderJob.objects.filter(
        policy=policy,
        invoice=inv,
        scheduled_date=job.scheduled_date,
        status=ReminderJob.Status.DISPATCHED,
    ).exclude(id=job.id).exists()
    if already_sent:
        block("A reminder for this occurrence has already been sent.")
        return

    # Balance snapshot check
    if abs(balance - job.balance_at_scheduling_minor) > 1:
        # Update snapshot and continue — amount will reflect current balance
        job.balance_at_scheduling_minor = balance
        job.save()

    # ── Render template ────────────────────────────────────────────────────
    from reminders.serializers import render_template
    context = {
        "customer_name": customer.name,
        "invoice_number": inv.invoice_number,
        "invoice_date": str(inv.invoice_date),
        "due_date": str(inv.due_date),
        "outstanding_amount": f"₹{balance / 100:,.2f}",
        "payment_reference_instructions": inv.invoice_number,
        "business_contact": org.business_email or org.name,
    }
    try:
        rendered_subject, rendered_body = render_template(
            policy.template.subject, policy.template.body, context
        )
    except ValueError as exc:
        block(f"Template render failed: {exc}")
        return

    # ── Create MessageLog with status=queued ───────────────────────────────
    log = MessageLog.objects.create(
        organization=org,
        reminder_job=job,
        invoice=inv,
        customer=customer,
        channel=channel,
        provider="email" if channel == "email" else "whatsapp",
        recipient=recipient,
        subject=rendered_subject[:998],
        body_preview=rendered_body[:200],
        status=MessageLog.Status.QUEUED,
    )

    # ── Send via configured provider ──────────────────────────────────────
    try:
        if channel == "email":
            from django.core.mail import send_mail
            from django.conf import settings as dj_settings
            send_mail(
                subject=rendered_subject,
                message=rendered_body,
                from_email=dj_settings.EMAIL_FROM,
                recipient_list=[recipient],
                fail_silently=False,
            )
        # Additional channels (WhatsApp etc.) added here when provider configured
        log.status = MessageLog.Status.SENT
        log.sent_at = timezone.now()
        log.save()

        job.status = ReminderJob.Status.DISPATCHED
        job.dispatched_at = timezone.now()
        job.save()

        AuditLog.objects.create(
            organization=org,
            action="reminder_job.dispatched",
            entity_type="reminder_job",
            entity_id=str(job.id),
            summary=f"Dispatched {channel} reminder for invoice {inv.invoice_number}",
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
            # Create notification for responsible user
            try:
                from notifications.models import Notification
                from core.models import Membership
                for m in Membership.objects.filter(
                    organization=org,
                    role__in=["owner", "manager"],
                    active=True,
                ).select_related("user"):
                    Notification.objects.get_or_create(
                        organization=org,
                        recipient=m.user,
                        event_type=Notification.EventType.REMINDER_FAILED,
                        entity_type="reminder_job",
                        entity_id=str(job.id),
                    )
            except Exception:
                pass
