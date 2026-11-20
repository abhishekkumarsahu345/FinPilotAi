"""
Management command to seed default reminder templates and create sample schedules.
Usage: python manage.py seed_reminder_templates --org-id=<uuid>
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import Organization, User
from reminders.models import ReminderTemplate, ReminderSchedule, ReminderStep


DEFAULT_TEMPLATES = [
    {
        "name": "Invoice Issue Notification",
        "tone": "issue",
        "subject": "Invoice {{invoice_number}} from {{business_name}}",
        "body": """Dear {{customer_name}},

Thank you for your business! Please find your invoice details below.

Invoice Number: {{invoice_number}}
Invoice Date: {{invoice_date}}
Due Date: {{due_date}}
Amount Due: {{outstanding_amount}}

Payment Instructions:
{{payment_reference_instructions}}

If you have any questions, please contact us at {{business_contact}}.

Best regards,
{{business_name}}""",
    },
    {
        "name": "Friendly Payment Reminder",
        "tone": "friendly",
        "subject": "Payment Reminder: Invoice {{invoice_number}}",
        "body": """Hello {{customer_name}},

This is a friendly reminder that payment for invoice {{invoice_number}} is due on {{due_date}}.

Outstanding Amount: {{outstanding_amount}}

Please arrange payment at your earliest convenience.

{{payment_reference_instructions}}

If you have already made the payment, please disregard this reminder.

Thank you!
{{business_name}}""",
    },
    {
        "name": "Gentle Overdue Reminder",
        "tone": "gentle",
        "subject": "Payment Overdue: Invoice {{invoice_number}}",
        "body": """Dear {{customer_name}},

We notice that invoice {{invoice_number}} (due date: {{due_date}}) is now overdue.

Outstanding Amount: {{outstanding_amount}}

We understand that payment delays can happen. If you have already made the payment, please disregard this reminder.

If you need to discuss payment arrangements, please contact us at {{business_contact}}.

Best regards,
{{business_name}}""",
    },
    {
        "name": "Final Payment Notice",
        "tone": "serious",
        "subject": "URGENT: Payment Required - Invoice {{invoice_number}}",
        "body": """Dear {{customer_name}},

IMPORTANT: Invoice {{invoice_number}} is significantly overdue (due date: {{due_date}}).

Outstanding Amount: {{outstanding_amount}}

We have sent multiple payment reminders. Please settle this invoice immediately to avoid any disruption to your account.

Payment Instructions:
{{payment_reference_instructions}}

If you have any questions or concerns, please contact us immediately at {{business_contact}}.

Urgent action required.

{{business_name}}""",
    },
]


class Command(BaseCommand):
    help = "Seed default reminder templates and create a sample 4-step reminder schedule"

    def add_arguments(self, parser):
        parser.add_argument(
            "--org-id",
            type=str,
            help="Organization UUID to create templates and schedule for",
        )
        parser.add_argument(
            "--skip-schedule",
            action="store_true",
            help="Skip creating sample schedule (only create templates)",
        )

    def handle(self, *args, **options):
        org_id = options.get("org_id")
        
        if not org_id:
            self.stdout.write(self.style.ERROR("Please provide --org-id=<uuid>"))
            return

        try:
            org = Organization.objects.get(id=org_id)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization with ID {org_id} does not exist")

        # Get first owner/manager for created_by
        membership = org.memberships.filter(role__in=["owner", "manager"], active=True).first()
        if not membership:
            raise CommandError(f"No active owner/manager found for organization {org.name}")
        
        creator = membership.user

        with transaction.atomic():
            # Create templates
            created_templates = []
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
                if created:
                    created_templates.append(template)
                    self.stdout.write(self.style.SUCCESS(f"✓ Created template: {template.name}"))
                else:
                    self.stdout.write(self.style.WARNING(f"- Template already exists: {template.name}"))

            # Create sample schedule if requested
            if not options.get("skip_schedule"):
                schedule_name = "Standard 4-Step Payment Reminder Workflow"
                
                schedule, created = ReminderSchedule.objects.get_or_create(
                    organization=org,
                    name=schedule_name,
                    defaults={
                        "enabled": True,
                        "send_hour_start": 10,  # 10 AM
                        "send_hour_end": 18,    # 6 PM
                        "skip_weekdays": [5, 6],  # Skip Saturday and Sunday
                        "created_by": creator,
                    }
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f"✓ Created schedule: {schedule.name}"))
                    
                    # Create 4 steps
                    steps_config = [
                        {
                            "step_number": 1,
                            "offset_from_issue": 0,  # Day of invoice issue
                            "tone": "issue",
                            "template_name": "Invoice Issue Notification",
                            "is_final_notice": False,
                        },
                        {
                            "step_number": 2,
                            "offset_from_due": -7,  # 7 days BEFORE due date
                            "tone": "friendly",
                            "template_name": "Friendly Payment Reminder",
                            "is_final_notice": False,
                        },
                        {
                            "step_number": 3,
                            "offset_from_due": 3,  # 3 days AFTER due date
                            "tone": "gentle",
                            "template_name": "Gentle Overdue Reminder",
                            "is_final_notice": False,
                        },
                        {
                            "step_number": 4,
                            "offset_from_due": 15,  # 15 days AFTER due date
                            "tone": "serious",
                            "template_name": "Final Payment Notice",
                            "is_final_notice": True,
                        },
                    ]
                    
                    for step_conf in steps_config:
                        template = ReminderTemplate.objects.get(
                            organization=org,
                            name=step_conf["template_name"]
                        )
                        
                        step, step_created = ReminderStep.objects.get_or_create(
                            schedule=schedule,
                            step_number=step_conf["step_number"],
                            defaults={
                                "offset_from_issue": step_conf.get("offset_from_issue"),
                                "offset_from_due": step_conf.get("offset_from_due"),
                                "tone": step_conf["tone"],
                                "template": template,
                                "approval_mode": "manual",  # Always start with manual approval
                                "enabled": True,
                                "is_final_notice": step_conf["is_final_notice"],
                            }
                        )
                        
                        if step_created:
                            offset_desc = (
                                f"{step_conf['offset_from_issue']} days from issue"
                                if "offset_from_issue" in step_conf
                                else f"{step_conf['offset_from_due']} days from due"
                            )
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  ✓ Step {step.step_number}: {offset_desc} - {template.name}"
                                )
                            )
                else:
                    self.stdout.write(self.style.WARNING(f"- Schedule already exists: {schedule.name}"))

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Successfully seeded reminder templates and schedule for {org.name}"
            )
        )
        self.stdout.write(
            self.style.WARNING(
                "\n⚠️  All reminder steps are set to MANUAL approval by default."
            )
        )
        self.stdout.write(
            "   To enable automatic sending for a step, use the API endpoint:"
        )
        self.stdout.write(
            "   POST /api/v1/reminders/steps/<step-id>/activate-auto/ with {'confirm': true}"
        )
