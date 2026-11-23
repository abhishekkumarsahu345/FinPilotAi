"""
Enhanced Celery tasks for the new ReminderSchedule/ReminderStep system.
Generates reminder jobs based on step offsets and handles approval workflow.
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


@shared_task(name="reminders.schedule_step_reminders")
def schedule_step_reminders():
    """
    Celery Beat job: runs hourly.
    For each enabled schedule, evaluates each step and creates ReminderJobs
    for eligible invoices based on step offset triggers.
    """
    from reminders.models import ReminderSchedule, ReminderStep, ReminderJob
    from core.models import Invoice, Organization
    from notifications.models import Notification
    from core.models import Membership

    today = date.today()
    scheduled_count = 0
    blocked_count = 0
    
    logger.info(f"[schedule_step_reminders] Starting reminder scheduling run for {today}")

    # Process all enabled schedules
    for schedule in ReminderSchedule.objects.filter(enabled=True).select_related("organization"):
        org = schedule.organization
        org_tz = pytz.timezone(org.timezone)
        
        logger.debug(f"Processing schedule {schedule.name} for {org.name}")
        
        # Process each enabled step in the schedule
        for step in schedule.steps.filter(enabled=True).select_related("template").order_by("step_number"):
            # Determine which invoices match this step's trigger
            invoices_to_remind = _find_eligible_invoices_for_step(org, step, today, schedule)
            
            for inv in invoices_to_remind:
                customer = inv.customer
                
                # Check customer-level exclusions
                if str(customer.id) in schedule.excluded_customer_ids:
                    continue
                if customer.opt_out:
                    continue
                
                # Check if customer has valid email
                if not customer.email:
                    continue
                
                # Calculate current outstanding balance
                active_paid = sum(
                    a.amount_minor for a in inv.allocations.filter(reversed_at__isnull=True)
                )
                outstanding = max(0, inv.total_minor - active_paid)
                
                if outstanding == 0:
                    continue  # Fully paid — no reminder needed
                
                # Build idempotency key
                idempotency_key = f"{schedule.id}:{step.id}:{inv.id}:{today}"
                
                # Check if job already exists
                if ReminderJob.objects.filter(idempotency_key=idempotency_key).exists():
                    continue
                
                # Calculate days overdue
                days_overdue = max(0, (today - inv.due_date).days) if inv.due_date < today else 0
                
                # Create snapshot
                try:
                    with transaction.atomic():
                        job = ReminderJob.objects.create(
                            organization=org,
                            schedule=schedule,
                            step=step,
                            invoice=inv,
                            customer=customer,
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
                        
                        # If automatic mode, dispatch immediately
                        if step.approval_mode == ReminderStep.ApprovalMode.AUTOMATIC:
                            from reminders.dispatch_tasks import dispatch_reminder_email
                            dispatch_reminder_email.apply_async(
                                args=[str(job.id)],
                                countdown=_calculate_dispatch_delay(schedule, org_tz, today),
                            )
                            scheduled_count += 1
                        else:
                            # Manual mode: create notification for approval
                            try:
                                finance_members = Membership.objects.filter(
                                    organization=org,
                                    role__in=["owner", "manager"],
                                    active=True,
                                ).select_related("user")
                                
                                for member in finance_members:
                                    Notification.objects.get_or_create(
                                        organization=org,
                                        recipient=member.user,
                                        event_type=Notification.EventType.REMINDER_AWAITING_APPROVAL,
                                        entity_type="reminder_job",
                                        entity_id=str(job.id),
                                        defaults={"payload": {"invoice_number": inv.invoice_number}},
                                    )
                            except Exception as e:
                                logger.warning(f"Failed to create notification for job {job.id}: {e}")
                            scheduled_count += 1

                except Exception as e:
                    logger.error(f"Failed to create reminder job for invoice {inv.id}: {e}")
                    blocked_count += 1

    logger.info(
        f"[schedule_step_reminders] Scheduled {scheduled_count} reminders, {blocked_count} blocked"
    )
    return {"scheduled": scheduled_count, "blocked": blocked_count}


def _find_eligible_invoices_for_step(org, step, today, schedule):
    """
    Find invoices that match the step's trigger offset.
    Returns QuerySet of Invoice objects.
    """
    from core.models import Invoice
    
    # Only process issued invoices (not drafts or voids)
    base_qs = Invoice.objects.filter(
        organization=org,
        status=Invoice.Status.ISSUED,
    ).select_related("customer").prefetch_related("allocations")
    
    if step.offset_from_due is not None:
        # Offset from due date
        # Negative offset = days before due date
        # Positive offset = days after due date
        target_due_date = today - timedelta(days=step.offset_from_due)
        return base_qs.filter(due_date=target_due_date)
    
    elif step.offset_from_issue is not None:
        # Offset from invoice issue date
        target_issue_date = today - timedelta(days=step.offset_from_issue)
        return base_qs.filter(invoice_date=target_issue_date)
    
    else:
        # Invalid step configuration
        logger.error(f"Step {step.id} has no offset configured")
        return Invoice.objects.none()


def _calculate_dispatch_delay(schedule, org_tz, target_date) -> int:
    """
    Calculate countdown (in seconds) to dispatch during business hours.
    Respects send_hour_start and send_hour_end.
    Returns 0 if should send immediately.
    """
    now = timezone.now()
    org_now = now.astimezone(org_tz)
    
    # Build target time today within business hours
    # Use send_hour_start as the default send time
    target_dt = org_now.replace(
        hour=schedule.send_hour_start,
        minute=0,
        second=0,
        microsecond=0,
    )
    
    # If already past, check if still within business hours
    if target_dt <= org_now:
        current_hour = org_now.hour
        if schedule.send_hour_start <= current_hour < schedule.send_hour_end:
            # Still within business hours, send now
            return 0
        else:
            # Past business hours, schedule for tomorrow
            target_dt += timedelta(days=1)
    
    # Check if target day is in skip_weekdays
    while target_dt.weekday() in (schedule.skip_weekdays or []):
        target_dt += timedelta(days=1)
    
    delay_seconds = int((target_dt - org_now).total_seconds())
    return max(0, delay_seconds)


@shared_task(name="reminders.cancel_reminders_for_paid_invoice")
def cancel_reminders_for_paid_invoice(invoice_id: str):
    """
    Cancel all pending reminders for an invoice that has been fully paid.
    Called when a payment is recorded that brings balance to zero.
    """
    from reminders.models import ReminderJob
    from core.models import Invoice
    
    try:
        invoice = Invoice.objects.get(id=invoice_id)
    except Invoice.DoesNotExist:
        return
    
    # Cancel all proposed/approved/scheduled jobs for this invoice
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
    Celery task: delete old blocked/rejected/failed/skipped jobs older than N days.
    Keeps dispatched jobs and message logs.
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
    
    logger.info(f"[cleanup_old_reminder_jobs] Deleted {deleted[0]} old reminder jobs")
    return {"deleted": deleted[0]}
