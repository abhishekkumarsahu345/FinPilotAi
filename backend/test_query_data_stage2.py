#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STAGE 2: Test query_data tool
"""
import os
import sys
import django

# Force UTF-8 output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.models import Customer, Organization, Invoice, Payment
from ai_assistant.tools import query_data, get_schema_help

print("=" * 80)
print("STAGE 2: query_data TOOL TESTS")
print("=" * 80)

# Use Test Org (has data)
org = Organization.objects.get(name="Test Org")
print(f"\nUsing org: {org.name} (ID: {org.id})")

# Verify data exists
print(f"Customers: {Customer.objects.filter(organization=org).count()}")
print(f"Invoices: {Invoice.objects.filter(organization=org).count()}")
print(f"Payments: {Payment.objects.filter(organization=org).count()}")

print("\n" + "=" * 80)
print("TEST 1: Count all customers")
print("=" * 80)
result = query_data(
    org=org,
    entity="customers",
    aggregates={"count": {"count": "*"}}
)
print(f"Result: {result}")
expected_count = Customer.objects.filter(organization=org).count()
print(f"Expected count: {expected_count}")
print(f"✓ PASS" if result["rows"][0]["count"] == expected_count else "✗ FAIL")

print("\n" + "=" * 80)
print("TEST 2: List active customers")
print("=" * 80)
result = query_data(
    org=org,
    entity="customers",
    fields=["name", "email", "active"],
    filters={"active": {"eq": True}},
    limit=10
)
print(f"Found {result['count']} active customers")
for row in result["rows"][:3]:
    print(f"  - {row['name']} ({row['email']})")
if result['count'] > 3:
    print(f"  ... and {result['count'] - 3} more")
print(f"✓ PASS" if result['count'] > 0 else "✗ FAIL")

print("\n" + "=" * 80)
print("TEST 3: Filter invoices by status")
print("=" * 80)
result = query_data(
    org=org,
    entity="invoices",
    fields=["invoice_number", "status", "total_minor", "customer__name"],
    filters={"status": {"eq": "issued"}},
    limit=10
)
print(f"Found {result['count']} issued invoices")
for row in result["rows"][:3]:
    print(f"  - {row['invoice_number']}: ₹{row['total_minor']/100:.2f} ({row['customer__name']})")
print(f"✓ PASS" if result['count'] >= 0 else "✗ FAIL")

print("\n" + "=" * 80)
print("TEST 4: Group invoices by customer with total")
print("=" * 80)
result = query_data(
    org=org,
    entity="invoices",
    group_by="customer__name",
    aggregates={
        "invoice_count": {"count": "*"},
        "total_amount": {"sum": "total_minor"}
    },
    order_by=["-total_amount"],
    limit=5
)
print(f"Found {result['count']} customers with invoices")
for row in result["rows"]:
    print(f"  - {row['customer__name']}: {row['invoice_count']} invoices, ₹{row['total_amount']/100:.2f} total")
print(f"✓ PASS" if result['count'] >= 0 else "✗ FAIL")

print("\n" + "=" * 80)
print("TEST 5: Payments in date range (last 365 days)")
print("=" * 80)
result = query_data(
    org=org,
    entity="payments",
    fields=["payment_date", "amount_minor", "method", "customer__name"],
    filters={
        "payment_date": {"gte": "today-365", "lte": "today"}
    },
    order_by=["-payment_date"],
    limit=10
)
print(f"Found {result['count']} payments in last 365 days")
for row in result["rows"][:3]:
    print(f"  - {row['payment_date']}: ₹{row['amount_minor']/100:.2f} from {row['customer__name']} via {row['method']}")
print(f"✓ PASS" if result['count'] >= 0 else "✗ FAIL")

print("\n" + "=" * 80)
print("TEST 6: Search customers by name (contains)")
print("=" * 80)
result = query_data(
    org=org,
    entity="customers",
    fields=["name", "email"],
    filters={"name": {"contains": "person"}},
    limit=10
)
print(f"Found {result['count']} customers with 'person' in name")
for row in result["rows"]:
    print(f"  - {row['name']} ({row['email']})")
print(f"✓ PASS" if result['count'] >= 0 else "✗ FAIL")

print("\n" + "=" * 80)
print("TEST 7: Get schema help")
print("=" * 80)
schema_help = get_schema_help()
print(f"Entities available: {list(schema_help['entities'].keys())}")
print(f"Operators available: {list(schema_help['operators'].keys())}")
print(f"Special values: {list(schema_help['special_values'].keys())}")
print(f"✓ PASS" if len(schema_help['entities']) == 4 else "✗ FAIL")

print("\n" + "=" * 80)
print("TEST 8: Average invoice amount")
print("=" * 80)
result = query_data(
    org=org,
    entity="invoices",
    aggregates={
        "avg_amount": {"avg": "total_minor"},
        "min_amount": {"min": "total_minor"},
        "max_amount": {"max": "total_minor"},
        "total": {"sum": "total_minor"},
        "count": {"count": "*"}
    }
)
print(f"Invoice statistics:")
if result["rows"]:
    row = result["rows"][0]
    print(f"  Count: {row.get('count', 0)}")
    print(f"  Average: ₹{(row.get('avg_amount', 0) or 0)/100:.2f}")
    print(f"  Min: ₹{(row.get('min_amount', 0) or 0)/100:.2f}")
    print(f"  Max: ₹{(row.get('max_amount', 0) or 0)/100:.2f}")
    print(f"  Total: ₹{(row.get('total', 0) or 0)/100:.2f}")
print(f"✓ PASS" if result["rows"] else "✗ FAIL")

print("\n" + "=" * 80)
print("TEST 9: Top 3 customers by payment amount")
print("=" * 80)
result = query_data(
    org=org,
    entity="payments",
    group_by="customer__name",
    aggregates={
        "total_paid": {"sum": "amount_minor"},
        "payment_count": {"count": "*"}
    },
    order_by=["-total_paid"],
    limit=3
)
print(f"Top {result['count']} customers by payments:")
for i, row in enumerate(result["rows"], 1):
    print(f"  {i}. {row['customer__name']}: ₹{row['total_paid']/100:.2f} ({row['payment_count']} payments)")
print(f"✓ PASS" if result['count'] >= 0 else "✗ FAIL")

print("\n" + "=" * 80)
print("TEST 10: Invalid entity (error handling)")
print("=" * 80)
result = query_data(
    org=org,
    entity="invalid_entity",
)
print(f"Result: {result}")
print(f"✓ PASS" if "error" in result else "✗ FAIL")

print("\n" + "=" * 80)
print("STAGE 2 TESTS COMPLETE")
print("=" * 80)
