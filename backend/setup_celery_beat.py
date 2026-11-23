"""
One-time setup script to configure Celery Beat periodic tasks.
Run after starting Django for the first time:
    python setup_celery_beat.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django_celery_beat.models import PeriodicTask, IntervalSchedule
import json

def setup_beat_tasks():
    """Configure periodic tasks for reminder scheduling."""
    
    # Create hourly schedule
    hourly_schedule, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.HOURS,
    )
    
    if created:
        print("✅ Created hourly schedule")
    
    # Create reminder scheduling task
    task, created = PeriodicTask.objects.get_or_create(
        name='Schedule Payment Reminders (Hourly)',
        defaults={
            'interval': hourly_schedule,
            'task': 'reminders.schedule_step_reminders',
            'enabled': True,
            'description': 'Evaluates all enabled reminder schedules and creates jobs for eligible invoices',
        }
    )
    
    if created:
        print("✅ Created periodic task: Schedule Payment Reminders")
    else:
        print("ℹ️  Periodic task already exists: Schedule Payment Reminders")
    
    # Create cleanup task (runs daily at 2 AM)
    daily_schedule, created = IntervalSchedule.objects.get_or_create(
        every=1,
        period=IntervalSchedule.DAYS,
    )
    
    cleanup_task, created = PeriodicTask.objects.get_or_create(
        name='Cleanup Old Reminder Jobs (Daily)',
        defaults={
            'interval': daily_schedule,
            'task': 'reminders.cleanup_old_reminder_jobs',
            'enabled': True,
            'args': json.dumps([90]),  # Keep 90 days
            'description': 'Deletes old blocked/rejected/failed reminder jobs',
        }
    )
    
    if created:
        print("✅ Created periodic task: Cleanup Old Reminder Jobs")
    else:
        print("ℹ️  Periodic task already exists: Cleanup Old Reminder Jobs")
    
    print("\n📋 Current Periodic Tasks:")
    for task in PeriodicTask.objects.all():
        status = "🟢 ENABLED" if task.enabled else "🔴 DISABLED"
        print(f"  {status} {task.name}")
        print(f"     Task: {task.task}")
        if task.interval:
            print(f"     Schedule: Every {task.interval.every} {task.interval.period}")
        print()

if __name__ == '__main__':
    print("Setting up Celery Beat periodic tasks...\n")
    setup_beat_tasks()
    print("\n✅ Celery Beat configuration complete!")
    print("\nTo start Celery Beat, run:")
    print("  celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler")
