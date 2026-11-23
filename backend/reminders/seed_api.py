"""
API endpoint to seed default reminder templates and create sample schedule.
POST /api/v1/reminders/seed-defaults/
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, status
from rest_framework.response import Response
from django.db import transaction

from core.permissions import HasOrganizationAccess, FINANCE_ROLES
from core.models import AuditLog
from .models import ReminderTemplate, ReminderSchedule, ReminderStep


DEFAULT_TEMPLATES = [
    {
        "name": "Invoice Issue Notification",
        "tone": "issue",
        "subject": "Invoice {{invoice_number}} from {{business_name}}",
        "body": "Thank you for your business! Invoice {{invoice_number}} dated {{invoice_date}} is due on {{due_date}}. Amount: {{outstanding_amount}}. {{payment_reference_instructions}}",
    },
    {
        "name": "Friendly Payment Reminder",
        "tone": "friendly",
        "subject": "Payment Reminder: Invoice {{invoice_number}}",
        "body": "Hello {{customer_name}}, friendly reminder that invoice {{invoice_number}} is due on {{due_date}}. Outstanding: {{outstanding_amount}}. {{payment_reference_instructions}}",
    },
    {
        "name": "Gentle Overdue Reminder",
        "tone": "gentle",
        "subject": "Payment Overdue: Invoice {{invoice_number}}",
        "body": "Dear {{customer_name}}, invoice {{invoice_number}} is now overdue (due: {{due_date}}). Outstanding: {{outstanding_amount}}. Please arrange payment. {{business_contact}}",
    },
    {
        "name": "Final Payment Notice",
        "tone": "serious",
        "subject": "URGENT: Payment Required - Invoice {{invoice_number}}",
        "body": "IMPORTANT: Invoice {{invoice_number}} is significantly overdue. Outstanding: {{outstanding_amount}}. Immediate action required. Contact: {{business_contact}}",
    },
]


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def seed_default_reminder_setup(request):
    """
    Seed default reminder templates and create a 4-step payment reminder schedule.
    Only finance roles can execute this.
    """
    if request.membership.role not in FINANCE_ROLES:
        return Response(
            {"detail": "Only Business Owner or Finance Manager can seed reminder setup."},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    org = request.membership.organization
    creator = request.user
    
    with transaction.atomic():
        # Create templates
        created_templates = {}
        for tpl_data in DEFAULT_TEMPLATES:
            template, created = ReminderTemplate.objects.get_or_create(
                organization=org,
                name=tpl_data["name"],
                defaults={
                    "channel": "email",
                    "subject": tpl_data["subject"],
                    "body": tpl_data["body"],
                    "created_by": creator,
                }
            )
            created_templates[tpl_data["tone"]] = template
        
        # Create standard 4-step schedule
        schedule_name = "Standard Payment Reminder Workflow"
        schedule, schedule_created = ReminderSchedule.objects.get_or_create(
            organization=org,
            name=schedule_name,
            defaults={
                "enabled": True,
                "send_hour_start": 10,
                "send_hour_end": 18,
                "skip_weekdays": [],  # Send all days (user can customize)
                "created_by": creator,
            }
        )
        
        steps_created = 0
        if schedule_created:
            # Step 1: Invoice issue (offset 0 from issue date)
            ReminderStep.objects.get_or_create(
                schedule=schedule,
                step_number=1,
                defaults={
                    "offset_from_issue": 0,
                    "tone": "issue",
                    "template": created_templates["issue"],
                    "approval_mode": "manual",
                    "enabled": True,
                }
            )
            steps_created += 1
            
            # Step 2: 7 days before due date
            ReminderStep.objects.get_or_create(
                schedule=schedule,
                step_number=2,
                defaults={
                    "offset_from_due": -7,
                    "tone": "friendly",
                    "template": created_templates["friendly"],
                    "approval_mode": "manual",
                    "enabled": True,
                }
            )
            steps_created += 1
            
            # Step 3: 3 days after due date
            ReminderStep.objects.get_or_create(
                schedule=schedule,
                step_number=3,
                defaults={
                    "offset_from_due": 3,
                    "tone": "gentle",
                    "template": created_templates["gentle"],
                    "approval_mode": "manual",
                    "enabled": True,
                }
            )
            steps_created += 1
            
            # Step 4: 15 days after due date (final notice)
            ReminderStep.objects.get_or_create(
                schedule=schedule,
                step_number=4,
                defaults={
                    "offset_from_due": 15,
                    "tone": "serious",
                    "template": created_templates["serious"],
                    "approval_mode": "manual",
                    "enabled": True,
                    "is_final_notice": True,
                }
            )
            steps_created += 1
            
            AuditLog.objects.create(
                organization=org,
                actor=creator,
                action="reminder_setup.seeded",
                entity_type="reminder_schedule",
                entity_id=str(schedule.id),
                summary=f"Seeded default reminder setup with {steps_created} steps",
            )
    
    return Response({
        "message": "Default reminder setup created successfully",
        "schedule_id": str(schedule.id),
        "schedule_name": schedule.name,
        "steps_created": steps_created,
        "templates_count": len(created_templates),
        "note": "All steps are set to manual approval by default. Enable automatic sending via step settings if desired.",
    })
