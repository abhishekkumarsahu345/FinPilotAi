#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STAGE 0: DIAGNOSE - Trace AI assistant requests end-to-end
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

from core.models import Customer, Organization, Membership, Invoice, Payment
from django.contrib.auth import get_user_model

User = get_user_model()

print("=" * 80)
print("STAGE 0: DATABASE STATE DIAGNOSIS")
print("=" * 80)

print("\n=== DATABASE COUNTS ===")
print(f"Organizations: {Organization.objects.count()}")
print(f"Users: {User.objects.count()}")
print(f"Memberships: {Membership.objects.count()}")
print(f"Total Customers: {Customer.objects.count()}")
print(f"Total Invoices: {Invoice.objects.count()}")
print(f"Total Payments: {Payment.objects.count()}")

print("\n=== PER ORGANIZATION ===")
for org in Organization.objects.all():
    print(f"\nOrg: {org.name} (ID: {org.id})")
    members = Membership.objects.filter(organization=org)
    print(f"  Members: {members.count()}")
    for m in members:
        print(f"    - {m.user.username} (role: {m.role})")
    
    customers = Customer.objects.filter(organization=org)
    print(f"  Customers: {customers.count()}")
    if customers.exists():
        for c in customers[:5]:  # Show first 5
            print(f"    - {c.name} (active: {c.active}, email: {c.email})")
        if customers.count() > 5:
            print(f"    ... and {customers.count() - 5} more")
    
    invoices = Invoice.objects.filter(organization=org)
    print(f"  Invoices: {invoices.count()}")
    
    payments = Payment.objects.filter(organization=org)
    print(f"  Payments: {payments.count()}")

print("\n" + "=" * 80)
print("SIMULATING REQUEST TRACES")
print("=" * 80)

# Create test user/org if none exist
if Organization.objects.count() == 0:
    print("\n⚠️  NO DATA: Database is empty. Creating test data...")
    org = Organization.objects.create(
        name="Test Org",
        default_currency="INR",
        timezone="Asia/Kolkata"
    )
    user = User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123"
    )
    Membership.objects.create(
        user=user,
        organization=org,
        role=Membership.Role.OWNER
    )
    Customer.objects.create(
        organization=org,
        name="Person 4",
        email="person4@example.com",
        active=True
    )
    print(f"✓ Created org: {org.name}")
    print(f"✓ Created user: {user.username}")
    print(f"✓ Created customer: Person 4")
else:
    # Use first org and user
    org = Organization.objects.first()
    membership = Membership.objects.filter(organization=org).first()
    if not membership:
        print("\n⚠️  NO MEMBERSHIP: Creating test user for existing org")
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        membership = Membership.objects.create(
            user=user,
            organization=org,
            role=Membership.Role.OWNER
        )
    user = membership.user

print(f"\nUsing org: {org.name} (ID: {org.id})")
print(f"Using user: {user.username}")

# Test each question through the code path
test_questions = [
    "how many total persons are there",
    "my invoices",
    "how much is overdue",
    "hi"
]

from ai_assistant.tools import AVAILABLE_TOOLS, search_customers, get_receivables_summary, get_customer_invoices

print("\n" + "=" * 80)
print("TOOL EXECUTION TRACES")
print("=" * 80)

for question in test_questions:
    print(f"\n{'='*80}")
    print(f"QUESTION: \"{question}\"")
    print(f"{'='*80}")
    
    q = question.lower()
    
    # Trace rule-based logic from _execute_rule_based
    print("\n[RULE-BASED KEYWORD MATCHING]")
    
    if any(k in q for k in ["how many customer", "total customer", "list customer", "all customer", "show customer", "count customer"]):
        print(f"  ✓ MATCHES: customer count/list keywords")
        print(f"  → Will call: search_customers(query='', active_only=True)")
        
        print("\n[TOOL EXECUTION: search_customers]")
        result = search_customers(org, query="", active_only=True)
        print(f"  Arguments: query='', active_only=True")
        print(f"  Result type: {type(result)}")
        print(f"  Result length: {len(result) if isinstance(result, list) else 'N/A'}")
        print(f"  Result: {result}")
        
        if isinstance(result, list) and len(result) == 0:
            print(f"\n  ⚠️  ISSUE FOUND: search_customers returned empty list")
            print(f"  DB query: Customer.objects.filter(organization={org.id}, name__icontains='')")
            
            # Check actual DB
            db_customers = Customer.objects.filter(organization=org)
            print(f"  Actual DB customers: {db_customers.count()}")
            if db_customers.exists():
                print(f"  Sample customers:")
                for c in db_customers[:3]:
                    print(f"    - {c.name} (active={c.active})")
        
    elif any(k in q for k in ["overdue", "outstanding", "owe", "receivable", "how much", "total amount"]):
        print(f"  ✓ MATCHES: overdue/receivables keywords")
        print(f"  → Will call: get_receivables_summary()")
        
        print("\n[TOOL EXECUTION: get_receivables_summary]")
        result = get_receivables_summary(org)
        print(f"  Result: {result}")
    
    elif any(k in q for k in ["my invoice", "invoices for"]):
        print(f"  ✓ MATCHES: invoice keywords")
        print(f"  → Will call: get_customer_invoices() BUT NEEDS customer_name")
        print(f"  ⚠️  ISSUE: 'my invoices' doesn't provide customer name")
        print(f"  Current logic expects customer name explicitly")
    
    elif any(k in q for k in ["hi", "hello", "hey"]):
        print(f"  ✗ NO MATCH: greeting not handled by keyword matching")
        print(f"  → Will call default: get_receivables_summary()")
    
    else:
        print(f"  ✗ NO MATCH: no keywords matched")
        print(f"  → Will call default: get_receivables_summary()")

print("\n" + "=" * 80)
print("ANSWER GENERATION TRACE")
print("=" * 80)

# Trace _rule_based_answer
from ai_assistant.views import _rule_based_answer

for question in ["how many total persons are there", "my invoices"]:
    print(f"\nQUESTION: \"{question}\"")
    
    # Simulate tool results
    if "how many" in question.lower():
        customers = search_customers(org, query="", active_only=True)
        tool_results = {"search_customers": customers}
        print(f"  Tool results: search_customers returned {len(customers) if isinstance(customers, list) else 'ERROR'} customers")
    else:
        tool_results = {}
    
    answer = _rule_based_answer(question, org, tool_results)
    print(f"  Generated answer: \"{answer}\"")
    
    if "No customers found" in answer:
        print(f"  ⚠️  ISSUE: Answer is 'No customers found'")
        print(f"  This comes from line in _rule_based_answer:")
        print(f"    if len(customer_search) == 0:")
        print(f"        return \"No customers found in your records.\"")

print("\n" + "=" * 80)
print("ROOT CAUSE ANALYSIS")
print("=" * 80)

# Check actual customer query
print("\nChecking customer query logic:")
customers_all = Customer.objects.filter(organization=org)
print(f"1. All customers in org: {customers_all.count()}")

customers_active = Customer.objects.filter(organization=org, active=True)
print(f"2. Active customers: {customers_active.count()}")

customers_icontains = Customer.objects.filter(organization=org, name__icontains="")
print(f"3. Customers with name__icontains='': {customers_icontains.count()}")

customers_icontains_active = Customer.objects.filter(organization=org, name__icontains="", active=True)
print(f"4. Active customers with name__icontains='': {customers_icontains_active.count()}")

# Trace search_customers function
print("\nTracing search_customers function:")
print("  Code path in tools.py:")
print("    customers_qs = Customer.objects.filter(")
print("        organization=org,")
print("        name__icontains=query  # query = ''")
print("    )")
print("    if active_only:")
print("        customers_qs = customers_qs.filter(active=True)")
print("    customers_qs = customers_qs.order_by('name')[:limit]")

actual_result = search_customers(org, query="", active_only=True, limit=20)
print(f"\n  Actual result: {len(actual_result) if isinstance(actual_result, list) else actual_result}")

if isinstance(actual_result, list) and len(actual_result) == 0 and customers_active.count() > 0:
    print("\n  ❌ BUG CONFIRMED: search_customers returns [] even though active customers exist")
elif isinstance(actual_result, list) and len(actual_result) > 0:
    print(f"\n  ✓ search_customers working correctly, returned {len(actual_result)} customers")
else:
    print(f"\n  ⚠️  Unexpected result type: {type(actual_result)}")

print("\n" + "=" * 80)
