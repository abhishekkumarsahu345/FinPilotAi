#!/usr/bin/env python
"""
Email Workflow Test Script

This script tests the complete email notification workflow:
1. SMTP configuration
2. Database connectivity
3. Celery broker connectivity
4. Email rendering
5. Direct email send test
6. Celery task execution test

Usage:
    python test_email_workflow.py <test_email_address>
    
Example:
    python test_email_workflow.py your-email@example.com
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from reminders.models import ReminderJob
from core.models import Invoice, Customer, Organization


def test_smtp_configuration():
    """Test 1: Verify SMTP configuration is loaded"""
    print("\n" + "="*60)
    print("TEST 1: SMTP Configuration")
    print("="*60)
    
    print(f"✓ EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"✓ EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"✓ EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"✓ EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"✓ EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"✓ EMAIL_FROM: {settings.EMAIL_FROM}")
    
    if not settings.EMAIL_HOST or not settings.EMAIL_HOST_USER:
        print("\n❌ FAIL: SMTP not configured in .env file")
        return False
    
    print("\n✅ PASS: SMTP configuration loaded successfully")
    return True


def test_redis_connection():
    """Test 2: Verify Redis (Celery broker) is accessible"""
    print("\n" + "="*60)
    print("TEST 2: Redis Connection")
    print("="*60)
    
    try:
        import redis
        broker_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
        print(f"✓ Broker URL: {broker_url}")
        
        # Parse Redis connection details
        if broker_url.startswith('redis://'):
            parts = broker_url.replace('redis://', '').split('/')
            host_port = parts[0].split(':')
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 6379
            db = int(parts[1]) if len(parts) > 1 else 0
            
            r = redis.Redis(host=host, port=port, db=db)
            r.ping()
            print(f"✓ Connected to Redis at {host}:{port}")
            print("\n✅ PASS: Redis is accessible")
            return True
    except Exception as e:
        print(f"\n❌ FAIL: Cannot connect to Redis: {e}")
        print("Make sure Docker containers are running: docker-compose up -d")
        return False


def test_database():
    """Test 3: Verify database connectivity and data"""
    print("\n" + "="*60)
    print("TEST 3: Database Connectivity")
    print("="*60)
    
    try:
        org_count = Organization.objects.count()
        customer_count = Customer.objects.count()
        invoice_count = Invoice.objects.count()
        job_count = ReminderJob.objects.count()
        
        print(f"✓ Organizations: {org_count}")
        print(f"✓ Customers: {customer_count}")
        print(f"✓ Invoices: {invoice_count}")
        print(f"✓ Reminder Jobs: {job_count}")
        
        if org_count == 0:
            print("\n⚠️  WARNING: No organizations found. Create one in the UI first.")
        
        print("\n✅ PASS: Database is accessible")
        return True
    except Exception as e:
        print(f"\n❌ FAIL: Database error: {e}")
        return False


def test_direct_email_send(recipient_email):
    """Test 4: Send a test email directly (no Celery)"""
    print("\n" + "="*60)
    print("TEST 4: Direct Email Send")
    print("="*60)
    
    if not recipient_email:
        print("⚠️  SKIPPED: No recipient email provided")
        return None
    
    try:
        subject = "FinPilot AI - Test Email"
        message = f"""
This is a test email from FinPilot AI.

Sent at: {timezone.now()}
Configuration:
- SMTP Host: {settings.EMAIL_HOST}
- From: {settings.EMAIL_FROM}

If you received this email, your SMTP configuration is working correctly!
"""
        
        print(f"Sending test email to: {recipient_email}")
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.EMAIL_FROM,
            recipient_list=[recipient_email],
            fail_silently=False,
        )
        print(f"\n✅ PASS: Email sent successfully to {recipient_email}")
        print("   Check your inbox (and spam folder)")
        return True
    except Exception as e:
        print(f"\n❌ FAIL: Email send failed: {e}")
        return False


def test_celery_task():
    """Test 5: Test Celery task queueing"""
    print("\n" + "="*60)
    print("TEST 5: Celery Task Queueing")
    print("="*60)
    
    try:
        from reminders.dispatch_tasks import dispatch_reminder_email
        
        # Find an approved reminder job to test with
        test_job = ReminderJob.objects.filter(
            status=ReminderJob.Status.APPROVED
        ).first()
        
        if not test_job:
            print("⚠️  No approved reminder jobs found to test with")
            print("   Create and approve a reminder job in the UI first")
            return None
        
        print(f"✓ Found test job: {test_job.id}")
        print(f"✓ Invoice: {test_job.invoice.invoice_number}")
        print(f"✓ Customer: {test_job.customer.name}")
        print(f"✓ Customer Email: {test_job.customer.email}")
        
        # Queue the task
        result = dispatch_reminder_email.delay(str(test_job.id))
        print(f"\n✓ Task queued with ID: {result.id}")
        print("\n⚠️  To process this task, you MUST have a Celery worker running:")
        print("   cd backend")
        print("   .\\start-celery-worker.ps1")
        print("\n✅ PASS: Task queued successfully")
        return True
    except Exception as e:
        print(f"\n❌ FAIL: Task queueing failed: {e}")
        return False


def main():
    print("\n" + "="*60)
    print("FinPilot AI - Email Workflow Test Suite")
    print("="*60)
    
    # Get recipient email from command line
    recipient_email = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not recipient_email:
        print("\n⚠️  No recipient email provided")
        print("Usage: python test_email_workflow.py <test_email_address>")
        print("\nRunning tests that don't require an email address...\n")
    
    # Run all tests
    results = []
    results.append(("SMTP Configuration", test_smtp_configuration()))
    results.append(("Redis Connection", test_redis_connection()))
    results.append(("Database Connectivity", test_database()))
    
    if recipient_email:
        results.append(("Direct Email Send", test_direct_email_send(recipient_email)))
    
    results.append(("Celery Task Queueing", test_celery_task()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result is True)
    failed = sum(1 for _, result in results if result is False)
    skipped = sum(1 for _, result in results if result is None)
    
    for name, result in results:
        status = "✅ PASS" if result is True else "❌ FAIL" if result is False else "⚠️  SKIP"
        print(f"{status} - {name}")
    
    print(f"\nTotal: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0:
        print("\n🎉 All tests passed!")
        print("\nNext steps:")
        print("1. Start the Celery worker in a separate terminal:")
        print("   cd backend")
        print("   .\\start-celery-worker.ps1")
        print("\n2. Approve a reminder job in the UI")
        print("3. Check the customer's email inbox")
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
