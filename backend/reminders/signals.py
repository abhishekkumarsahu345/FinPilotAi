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
    # Only process issued invoices
    if instance.status != Invoice.Status.ISSUED:
        return
    
    # Check if this is a status transition (not a new invoice creation)
    # We need to check if a step 1 job already exists to avoid duplicates
    
    # Get the organization's default reminder schedule
    try:
        schedule = ReminderSchedule.objects.filter(
            organization=instance.organization,
            enabled=True
        ).first()
        
        if not schedule:
            logger.debug(f"No enabled reminder schedule for {instance.organization}")
            return
        
        # Get step 1 (offset_from_issue=0, the initial invoice notification)
        step = schedule.steps.filter(
            step_number=1,
            enabled=True,
            offset_from_issue=0  # Initial invoice email
        ).first()
        
        if not step:
            logger.debug(f"No step 1 (initial invoice) configured for schedule {schedule.name}")
            return
        
        # Check customer eligibility
        customer = instance.customer
        if str(customer.id) in schedule.excluded_customer_ids:
            logger.debug(f"Customer {customer.name} is excluded from reminders")
            return
        if customer.opt_out:
            logger.debug(f"Customer {customer.name} has opted out of reminders")
            return
        if not customer.email:
            logger.debug(f"Customer {customer.name} has no email address")
            return
        
        # Check if invoice is already fully paid
        active_paid = sum(
            a.amount_minor for a in instance.allocations.filter(reversed_at__isnull=True)
        )
        outstanding = max(0, instance.total_minor - active_paid)
        if outstanding == 0:
            logger.debug(f"Invoice {instance.invoice_number} is already fully paid")
            return
        
        # Check if step 1 job already exists for this invoice
        today = date.today()
        idempotency_key = f"{schedule.id}:{step.id}:{instance.id}:{today}"
        
        if ReminderJob.objects.filter(idempotency_key=idempotency_key).exists():
            logger.debug(f"Initial invoice email already exists for {instance.invoice_number}")
            return
        
        # Create the initial invoice email job
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
                status=ReminderJob.Status.PROPOSED,  # Always require manual approval for initial email
            )
            
            # Create notification for finance team to approve
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
                                "step": "Initial Invoice Email"
                            }
                        },
                    )
                    
            except Exception as e:
                logger.warning(f"Failed to create notification for initial invoice email: {e}")
            
            logger.info(f"Created initial invoice email job for {instance.invoice_number}")
            
    except Exception as e:
        logger.error(f"Failed to create initial invoice email for {instance.invoice_number}: {e}")


@receiver(post_save, sender=PaymentAllocation)
def check_invoice_paid_and_cancel_reminders(sender, instance, created, **kwargs):
    """
    When a payment is allocated to an invoice, check if the invoice is now fully paid.
    If yes, cancel all pending reminder jobs for that invoice.
    """
    if not created and instance.reversed_at is not None:
        # Payment was reversed, don't cancel reminders
        return
    
    invoice = instance.invoice
    
    # Calculate current outstanding
    active_paid = sum(
        a.amount_minor for a in invoice.allocations.filter(reversed_at__isnull=True)
    )
    outstanding = max(0, invoice.total_minor - active_paid)
    
    if outstanding == 0:
        # Invoice is now fully paid — cancel all pending reminders
        logger.info(f"Invoice {invoice.invoice_number} is now fully paid, cancelling pending reminders")
        
        # Import task asynchronously to avoid circular import
        try:
            from reminders.schedule_tasks import cancel_reminders_for_paid_invoice
            cancel_reminders_for_paid_invoice.delay(str(invoice.id))
        except Exception as e:
            logger.error(f"Failed to cancel reminders for paid invoice {invoice.id}: {e}")
