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
    active_paid = sum(
        a.amount_minor for a in inv.allocations.filter(reversed_at__isnull=True)
    )
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

    # Check for duplicate send
    already_sent = ReminderJob.objects.filter(
        schedule=schedule,
        step=step,
        invoice=inv,
        status=ReminderJob.Status.DISPATCHED,
    ).exclude(id=job.id).exists()
    if already_sent:
        block("A reminder for this step and invoice has already been sent.")
        return

    # Update balance snapshot if changed significantly
    if abs(outstanding - job.balance_at_scheduling_minor) > 1:
        job.balance_at_scheduling_minor = outstanding
        job.snapshot_outstanding_minor = outstanding
        job.snapshot_paid_minor = active_paid
        job.save()

    # ── Build rich email content ────────────────────────────────────────────
    try:
        context = build_invoice_context(inv, customer, org)
        
        # Determine tone from step
        tone = step.tone if step.tone else 'friendly'
        
        # Generate subject and HTML body
        subject = generate_email_subject(context, tone)
        html_body = render_html_email_body(context, tone)
        
        # Apply custom intro/closing if provided by approver
        if job.approved_custom_intro:
            # Insert custom intro after greeting
            intro_marker = "<p>This is a friendly reminder"
            if intro_marker in html_body:
                html_body = html_body.replace(intro_marker, f"<p>{job.approved_custom_intro}</p><p>This is a friendly reminder", 1)
        
        if job.approved_custom_closing:
            # Insert custom closing before "Best regards"
            closing_marker = '<p style="margin-top: 32px;">Best regards,'
            if closing_marker in html_body:
                html_body = html_body.replace(closing_marker, f"<p>{job.approved_custom_closing}</p>{closing_marker}")
        
    except Exception as exc:
        block(f"Email rendering failed: {exc}")
        logger.exception(f"Email rendering failed for job {job.id}")
        return

    # ── Create MessageLog with status=queued ───────────────────────────────
    log = MessageLog.objects.create(
        organization=org,
        reminder_job=job,
        invoice=inv,
        customer=customer,
        channel="email",
        provider="email",
        recipient=customer.email,
        subject=subject[:998],
        body_preview=context['outstanding_amount'] + " outstanding",
        status=MessageLog.Status.QUEUED,
    )

    # ── Send via configured provider ──────────────────────────────────────
    try:
        from django.core.mail import send_mail
        
        send_mail(
            subject=subject,
            message="",  # Plain text fallback (empty for HTML-only)
            from_email=dj_settings.EMAIL_FROM,
            recipient_list=[customer.email],
            html_message=html_body,
            fail_silently=False,
        )
        
        # Update MessageLog and Job status
        log.status = MessageLog.Status.SENT
        log.sent_at = timezone.now()
        log.save()

        # Update job with sent snapshot
        job.status = ReminderJob.Status.DISPATCHED
        job.dispatched_at = timezone.now()
        job.sent_total_minor = inv.total_minor
        job.sent_paid_minor = active_paid
        job.sent_outstanding_minor = outstanding
        job.sent_due_date = inv.due_date
        job.sent_days_overdue = context['days_overdue']
        job.sent_html_body = html_body[:5000]  # Store preview
        job.save()

        AuditLog.objects.create(
            organization=org,
            action="reminder_job.dispatched",
            entity_type="reminder_job",
            entity_id=str(job.id),
            summary=f"Dispatched email reminder for invoice {inv.invoice_number} (₹{outstanding/100:,.2f} outstanding)",
        )
        
        logger.info(f"Successfully dispatched reminder email for invoice {inv.invoice_number}")

    except Exception as exc:
        log.error_detail = str(exc)[:500]
        retry_delay = 30 * (2 ** self.request.retries)
        
        if self.request.retries < self.max_retries:
            log.retry_count = self.request.retries + 1
            log.status = MessageLog.Status.QUEUED
            log.save()
            job.retry_count += 1
            job.save()
            logger.warning(f"Email send failed for job {job.id}, retrying in {retry_delay}s: {exc}")
            raise self.retry(exc=exc, countdown=min(retry_delay, 1800))
        else:
            log.status = MessageLog.Status.FAILED
            log.save()
            job.status = ReminderJob.Status.FAILED
            job.save()
            
            logger.error(f"Email send failed permanently for job {job.id}: {exc}")
            
            # Create notification for responsible users
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
