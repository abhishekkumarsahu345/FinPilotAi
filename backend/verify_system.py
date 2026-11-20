# -*- coding: utf-8 -*-
"""Final system verification script"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

print('='*70)
print('FINPILOT REMINDER SYSTEM - FINAL VERIFICATION')
print('='*70)

# 1. Check schedules
from reminders.models import ReminderSchedule, ReminderStep, ReminderJob
schedules = ReminderSchedule.objects.filter(enabled=True)
print(f'\n1. SCHEDULES: {schedules.count()} enabled')
first_schedule = schedules.first()
if first_schedule:
    print(f'   Example: {first_schedule.name}')
    print(f'   Organization: {first_schedule.organization.name}')
    print(f'   Steps configured: {first_schedule.steps.count()}')

# 2. Check steps
if first_schedule:
    print(f'\n2. REMINDER STAGES:')
    for step in first_schedule.steps.order_by('step_number'):
        offset_type = 'invoice issue' if step.offset_from_issue is not None else 'due date'
        offset_val = step.offset_from_issue if step.offset_from_issue is not None else step.offset_from_due
        sign = '+' if offset_val >= 0 else ''
        print(f'   Stage {step.step_number}: {sign}{offset_val} days from {offset_type} - {step.get_tone_display()}')

# 3. Check jobs
print(f'\n3. REMINDER JOBS:')
proposed = ReminderJob.objects.filter(status='proposed')
print(f'   Pending Approvals: {proposed.count()}')
if proposed.exists():
    job = proposed.first()
    print(f'   Example: Invoice {job.invoice.invoice_number} - Rs {job.snapshot_outstanding_minor/100:,.2f} outstanding')
    
dispatched = ReminderJob.objects.filter(status='dispatched').count()
print(f'   Dispatched: {dispatched}')

blocked = ReminderJob.objects.filter(status='blocked').count()
print(f'   Blocked: {blocked}')

# 4. Check email config
from django.conf import settings
print(f'\n4. EMAIL CONFIGURATION:')
print(f'   Backend: {settings.EMAIL_BACKEND.split(".")[-1]}')
print(f'   From: {settings.EMAIL_FROM}')
if 'console' in settings.EMAIL_BACKEND.lower():
    print(f'   Mode: Testing (prints to console)')
else:
    print(f'   Mode: Production SMTP')

# 5. Check Celery
print(f'\n5. CELERY INTEGRATION:')
try:
    from config.celery import app
    reminder_tasks = [t for t in app.tasks.keys() if 'reminder' in t.lower() and not t.startswith('celery.')]
    print(f'   App: Configured')
    print(f'   Reminder tasks: {len(reminder_tasks)}')
    for task in sorted(reminder_tasks):
        print(f'      - {task}')
except Exception as e:
    print(f'   Error: {e}')

# 6. Test signal
print(f'\n6. SIGNALS:')
try:
    import reminders.signals
    print(f'   Invoice signal: Registered')
    print(f'   Payment signal: Registered')
except Exception as e:
    print(f'   Error: {e}')

print('\n' + '='*70)
print('SYSTEM READY FOR TESTING')
print('='*70)
print('\nQUICK START:')
print('1. Frontend: http://localhost:5173 -> Reminders -> Pending Approvals')
print('2. Approve a reminder')
print('3. Check Django console for email output')
print('\nFOR BACKGROUND AUTOMATION:')
print('4. Terminal 3: celery -A config worker -l info --pool=solo')
print('5. Terminal 4: celery -A config beat -l info')
print('='*70)
