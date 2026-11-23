# -*- coding: utf-8 -*-
"""Simple test to create an invoice and check reminder creation"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from datetime import date, timedelta
from decimal import Decimal
from core.models import Organization, Customer, Invoice, InvoiceItem
from reminders.models import ReminderJob, ReminderSchedule

print("=" * 60)
print("Testing Reminder Creation")
print("=" * 60)

# Get org and user
org = Organization.objects.filter(status='active').first()
user = org.memberships.filter(active=True).first().user
print(f"Organization: {org.name}")
print(f"User: {user.email}")

# Get schedule
schedule = ReminderSchedule.objects.filter(organization=org, enabled=True).first()
print(f"Schedule: {schedule.name} with {schedule.steps.count()} steps")

# Get or create customer
customer, _ = Customer.objects.get_or_create(
    organization=org,
    email="test@example.com",
    defaults={'name': 'Test Customer', 'opt_out': False}
)
print(f"Customer: {customer.name}")

# Create invoice
today = date.today()
invoice = Invoice.objects.create(
    organization=org,
    customer=customer,
    invoice_number=f"TEST-{today.strftime('%Y%m%d')}",
    invoice_date=today,
    due_date=today + timedelta(days=30),
    status='draft',
    subtotal_minor=100000,
    tax_minor=18000,
    total_minor=118000,
    created_by=user,
)

InvoiceItem.objects.create(
    invoice=invoice,
    description="Test Item",
    quantity=Decimal('1.00'),
    unit_price_minor=100000,
    line_total_minor=100000,
    gst_rate_bps=1800,
    gst_tax_minor=18000,
    sort_order=1,
)

print(f"\nCreated invoice: {invoice.invoice_number} (status: {invoice.status})")

# Change to issued
invoice.status = 'issued'
invoice.save()
print(f"Changed status to: {invoice.status}")

# Check for reminder job
import time
time.sleep(2)
job = ReminderJob.objects.filter(invoice=invoice, step__step_number=1).first()

if job:
    print(f"\nSUCCESS: Reminder job created!")
    print(f"Job ID: {job.id}")
    print(f"Status: {job.status}")
    print(f"Outstanding: Rs {job.snapshot_outstanding_minor/100:.2f}")
else:
    print(f"\nNO REMINDER JOB FOUND")
    
print("\n" + "=" * 60)
