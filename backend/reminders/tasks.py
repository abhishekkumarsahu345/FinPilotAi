"""
Celery tasks for reminder scheduling and delivery orchestration.
"""
import logging
from datetime import date, datetime, timedelta
from typing import Optional

import pytz
from celery import shared_task
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="reminders.schedule_reminders")
def schedule_reminders():
    """
    Celery Beat job: runs every hour (or as configured).
    For each enabled policy, finds eligible invoices and creates ReminderJobs.
    Uses idempotency key to prevent duplicates.
    """
    from reminders.models import ReminderPolicy, ReminderJob
    from core.models import Invoice, Organization
    from notifications.models import Notification
    from core.models import Membership

    today = date.today()
    scheduled_count = 0
    blocked_count = 0
    logger.info(f"[schedule_reminders] Starting reminder scheduling run for {today}")

    for policy in ReminderPolicy.objects.filter(enabled=True).select_related(
        "organization", "template"
    ):
        org = policy.organization
        org_tz = pytz.timezone(org.timezone)
        
        # Calculate trigger date: offset days from due date
        trigger_date = today + timedelta(days=-policy.trigger_offset_days)

        # Find eligible invoices
        applicable_statuses = policy.applicable_statuses or ["issued"]
        invoices = Invoice.objects.filter(
            organization=org,
            status__in=applicable_statuses,
            due_date=trigger_date,
        ).select_related("customer").prefetch_related("allocations")

        for inv in invoices:
            customer = inv.customer

            # Check customer-level exclusions
            if str(customer.id) in policy.excluded_customer_ids:
                continue
            if customer.opt_out:
                continue
            
            # Check channel contact
            if policy.channel == "email" and not customer.email:
                continue
            if policy.channel == "whatsapp" and not customer.phone:
                continue

            # Calculate current outstanding balance
            active_paid = sum(
                a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
            )
            balance = max(0, inv.total_minor - active_paid)
            
            if balance == 0:
                continue  # Fully paid — no reminder needed

            # Check frequency limit: count previous reminders for this invoice
            previous_reminder_count = ReminderJob.objects.filter(
                organization=org,
                invoice=inv,
                policy=policy,
                status__in=[
                    ReminderJob.Status.DISPATCHED,
                    ReminderJob.Status.APPROVED,
                    ReminderJob.Status.SCHEDULED,
                ],
            ).count()

            if previous_reminder_count >= policy.max_attempts:
                continue

            # Check min_days_between_reminders
            if policy.min_days_between_reminders > 0:
                last_dispatched = ReminderJob.objects.filter(
                    organization=org,
                    invoice=inv,
                    policy=policy,
                    status=ReminderJob.Status.DISPATCHED,
                ).order_by("-dispatched_at").first()
                
                if last_dispatched and last_dispatched.dispatched_at:
                    days_since = (timezone.now() - last_dispatched.dispatched_at).days
                    if days_since < policy.min_days_between_reminders:
                        continue

            # Create idempotency key
            idempotency_key = f"{policy.id}:{inv.id}:{today}"

            # Check if job already exists
            existing = ReminderJob.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                continue

            # Create job
            try:
                with transaction.atomic():
                    job = ReminderJob.objects.create(
                        organization=org,
                        policy=policy,
                        invoice=inv,
                        customer=customer,
                        scheduled_date=today,
                        balance_at_scheduling_minor=balance,
                        idempotency_key=idempotency_key,
                        status=(
                            ReminderJob.Status.SCHEDULED
                            if policy.approval_mode == ReminderPolicy.ApprovalMode.AUTOMATIC
                            else ReminderJob.Status.PROPOSED
                        ),
                    )
                    
                    # If automatic mode, dispatch immediately
                    if policy.approval_mode == ReminderPolicy.ApprovalMode.AUTOMATIC:
                        from messaging.tasks import dispatch_reminder_job
                        dispatch_reminder_job.apply_async(
                            args=[str(job.id)],
                            countdown=_calculate_dispatch_delay(policy, org_tz),
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
        f"[schedule_reminders] Scheduled {scheduled_count} reminders, {blocked_count} blocked"
    )
    return {"scheduled": scheduled_count, "blocked": blocked_count}


def _calculate_dispatch_delay(policy, org_tz) -> int:
    """
    Calculate countdown (in seconds) to dispatch at the configured send time.
    Respects quiet hours. Returns 0 if should send immediately.
    """
    now = timezone.now()
    org_now = now.astimezone(org_tz)
    
    # Build target time today
    target = org_now.replace(
        hour=policy.send_hour,
        minute=policy.send_minute,
        second=0,
        microsecond=0,
    )
    
    # If already past, schedule for tomorrow
    if target <= org_now:
        target += timedelta(days=1)
    
    # Check quiet hours
    if policy.quiet_hours_start is not None and policy.quiet_hours_end is not None:
        target_hour = target.hour
        quiet_start = policy.quiet_hours_start
        quiet_end = policy.quiet_hours_end
        
        # Handle wrap-around (e.g. 22:00 to 08:00)
        if quiet_start > quiet_end:
            in_quiet = target_hour >= quiet_start or target_hour < quiet_end
        else:
            in_quiet = quiet_start <= target_hour < quiet_end
        
        if in_quiet:
            # Move to end of quiet hours
            target = target.replace(hour=quiet_end, minute=0, second=0)
            if target <= org_now:
                target += timedelta(days=1)
    
    delay_seconds = int((target - org_now).total_seconds())
    return max(0, delay_seconds)


@shared_task(name="reminders.cleanup_old_jobs")
def cleanup_old_jobs(days_to_keep: int = 90):
    """
    Celery task: delete old blocked/rejected/failed jobs older than N days.
    Keeps dispatched jobs and message logs forever (or until retention policy).
    """
    from reminders.models import ReminderJob
    
    cutoff = timezone.now() - timedelta(days=days_to_keep)
    deleted = ReminderJob.objects.filter(
        status__in=[
            ReminderJob.Status.BLOCKED,
            ReminderJob.Status.REJECTED,
            ReminderJob.Status.FAILED,
        ],
        created_at__lt=cutoff,
    ).delete()
    
    logger.info(f"[cleanup_old_jobs] Deleted {deleted[0]} old reminder jobs")
    return {"deleted": deleted[0]}


@shared_task(name="reminders.check_plan_limits")
def check_plan_limits(org_id: str) -> dict:
    """
    Check if organization has exceeded its plan's monthly message limit.
    Called before dispatching automatic reminders.
    Returns {"allowed": bool, "remaining": int, "limit": int}
    """
    from core.models import Organization
    from subscriptions.models import Subscription
    from messaging.models import MessageLog
    from datetime import datetime
    
    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return {"allowed": False, "remaining": 0, "limit": 0, "error": "Organization not found"}
    
    # Get active subscription
    subscription = Subscription.objects.filter(
        organization=org,
        status__in=["trial", "active"],
    ).select_related("plan").order_by("-created_at").first()
    
    if not subscription:
        # No subscription — default to trial limits (or block if required)
        return {"allowed": False, "remaining": 0, "limit": 0, "error": "No active subscription"}
    
    plan = subscription.plan
    limit = plan.max_messages_per_month
    
    if limit == 0:
        # Unlimited
        return {"allowed": True, "remaining": -1, "limit": 0}
    
    # Count messages sent this month
    start_of_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sent_this_month = MessageLog.objects.filter(
        organization=org,
        queued_at__gte=start_of_month,
        status__in=["sent", "delivered"],
    ).count()
    
    remaining = max(0, limit - sent_this_month)
    allowed = remaining > 0
    
    return {"allowed": allowed, "remaining": remaining, "limit": limit, "used": sent_this_month}
