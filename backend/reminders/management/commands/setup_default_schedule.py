"""
Management command to create or update the default 6-stage reminder schedule.

Usage:
    python manage.py setup_default_schedule --org=<organization_id>
    python manage.py setup_default_schedule --all-orgs
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from core.models import Organization
from reminders.models import ReminderSchedule, ReminderStep, ReminderTemplate


class Command(BaseCommand):
    help = 'Create or update the default 6-stage invoice reminder schedule'

    def add_arguments(self, parser):
        parser.add_argument(
            '--org',
            type=str,
            help='Organization ID to create schedule for',
        )
        parser.add_argument(
            '--all-orgs',
            action='store_true',
            help='Create schedules for all organizations',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Replace existing schedules (use with caution)',
        )

    def handle(self, *args, **options):
        org_id = options.get('org')
        all_orgs = options.get('all_orgs')
        force = options.get('force', False)
        
        if not org_id and not all_orgs:
            raise CommandError('Must specify either --org=<id> or --all-orgs')
        
        # Get organizations to process
        if all_orgs:
            orgs = Organization.objects.filter(status=Organization.Status.ACTIVE)
        else:
            try:
                orgs = [Organization.objects.get(id=org_id)]
            except Organization.DoesNotExist:
                raise CommandError(f'Organization {org_id} not found')
        
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        for org in orgs:
            try:
                result = self._setup_schedule_for_org(org, force)
                if result == 'created':
                    created_count += 1
                elif result == 'updated':
                    updated_count += 1
                else:
                    skipped_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Failed to setup schedule for {org.name}: {e}'))
        
        self.stdout.write(self.style.SUCCESS(
            f'\nSummary: {created_count} created, {updated_count} updated, {skipped_count} skipped'
        ))

    def _setup_schedule_for_org(self, org, force=False):
        """Create or update the default 6-stage reminder schedule for an organization."""
        
        # Check if schedule already exists
        existing = ReminderSchedule.objects.filter(
            organization=org,
            name="Default Invoice Reminders"
        ).first()
        
        if existing and not force:
            self.stdout.write(self.style.WARNING(
                f'Schedule already exists for {org.name}, use --force to replace'
            ))
            return 'skipped'
        
        # Get a system user for created_by (use first owner or any user)
        creator = org.memberships.filter(role='owner', active=True).first()
        if not creator:
            creator = org.memberships.first()
        if not creator:
            self.stdout.write(self.style.ERROR(f'No users found for organization {org.name}'))
            return 'skipped'
        
        user = creator.user
        
        with transaction.atomic():
            # Create or update templates
            templates = self._create_default_templates(org, user)
            
            # Create or update schedule
            if existing:
                schedule = existing
                schedule.enabled = True
                schedule.send_hour_start = 10
                schedule.send_hour_end = 18
                schedule.skip_weekdays = [6]  # Skip Sunday
                schedule.save()
                action = 'updated'
            else:
                schedule = ReminderSchedule.objects.create(
                    organization=org,
                    name="Default Invoice Reminders",
                    enabled=True,
                    send_hour_start=10,
                    send_hour_end=18,
                    skip_weekdays=[6],  # Skip Sunday
                    created_by=user,
                )
                action = 'created'
            
            # Ensure this is marked as the default schedule
            ReminderSchedule.objects.filter(
                organization=org,
                is_default=True,
            ).exclude(id=schedule.id).update(is_default=False)
            schedule.is_default = True
            schedule.save(update_fields=["is_default"])
            
            # Delete existing steps if force update
            if existing and force:
                schedule.steps.all().delete()
            
            # Create the 6 stages
            stages = [
                {
                    'step_number': 1,
                    'offset_from_issue': 0,  # On invoice creation
                    'offset_from_due': None,
                    'tone': 'issue',
                    'template': templates['issue'],
                    'description': 'Initial invoice email sent when invoice is issued'
                },
                {
                    'step_number': 2,
                    'offset_from_issue': None,
                    'offset_from_due': -7,  # 7 days before due date
                    'tone': 'friendly',
                    'template': templates['friendly'],
                    'description': 'First payment reminder (7 days before due)'
                },
                {
                    'step_number': 3,
                    'offset_from_issue': None,
                    'offset_from_due': -3,  # 3 days before due date
                    'tone': 'friendly',
                    'template': templates['friendly'],
                    'description': 'Second payment reminder (3 days before due)'
                },
                {
                    'step_number': 4,
                    'offset_from_issue': None,
                    'offset_from_due': 0,  # On due date
                    'tone': 'gentle',
                    'template': templates['gentle'],
                    'description': 'Payment due notification (on due date)'
                },
                {
                    'step_number': 5,
                    'offset_from_issue': None,
                    'offset_from_due': 3,  # 3 days after due date
                    'tone': 'gentle',
                    'template': templates['gentle'],
                    'description': 'Overdue payment reminder (3 days after due)'
                },
                {
                    'step_number': 6,
                    'offset_from_issue': None,
                    'offset_from_due': 15,  # 15 days after due date
                    'tone': 'serious',
                    'template': templates['serious'],
                    'description': 'Final payment reminder (15 days after due)',
                    'is_final': True
                },
            ]
            
            for stage in stages:
                ReminderStep.objects.create(
                    schedule=schedule,
                    step_number=stage['step_number'],
                    offset_from_issue=stage['offset_from_issue'],
                    offset_from_due=stage['offset_from_due'],
                    tone=stage['tone'],
                    template=stage['template'],
                    approval_mode=ReminderStep.ApprovalMode.MANUAL,  # All require manual approval
                    enabled=True,
                    is_final_notice=stage.get('is_final', False),
                )
            
            self.stdout.write(self.style.SUCCESS(
                f'{action.capitalize()} 6-stage reminder schedule for {org.name}'
            ))
            
            return action

    def _create_default_templates(self, org, user):
        """Create default email templates for each tone."""
        templates = {}
        
        # Template 1: Invoice Issue Notification
        issue_template, _ = ReminderTemplate.objects.get_or_create(
            organization=org,
            name="Invoice Issue Notification",
            channel=ReminderTemplate.Channel.EMAIL,
            defaults={
                'subject': 'Invoice {invoice_number} from {business_name}',
                'body': 'Template body — will be replaced by HTML renderer',
                'active': True,
                'created_by': user,
            }
        )
        templates['issue'] = issue_template
        
        # Template 2: Friendly Reminder
        friendly_template, _ = ReminderTemplate.objects.get_or_create(
            organization=org,
            name="Friendly Payment Reminder",
            channel=ReminderTemplate.Channel.EMAIL,
            defaults={
                'subject': 'Payment Reminder: Invoice {invoice_number}',
                'body': 'Template body — will be replaced by HTML renderer',
                'active': True,
                'created_by': user,
            }
        )
        templates['friendly'] = friendly_template
        
        # Template 3: Gentle Reminder (overdue)
        gentle_template, _ = ReminderTemplate.objects.get_or_create(
            organization=org,
            name="Gentle Overdue Reminder",
            channel=ReminderTemplate.Channel.EMAIL,
            defaults={
                'subject': 'Payment Overdue: Invoice {invoice_number}',
                'body': 'Template body — will be replaced by HTML renderer',
                'active': True,
                'created_by': user,
            }
        )
        templates['gentle'] = gentle_template
        
        # Template 4: Serious/Final Notice
        serious_template, _ = ReminderTemplate.objects.get_or_create(
            organization=org,
            name="Final Payment Notice",
            channel=ReminderTemplate.Channel.EMAIL,
            defaults={
                'subject': 'URGENT: Final Payment Notice - Invoice {invoice_number}',
                'body': 'Template body — will be replaced by HTML renderer',
                'active': True,
                'created_by': user,
            }
        )
        templates['serious'] = serious_template
        
        return templates
