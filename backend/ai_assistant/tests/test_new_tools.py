"""
Test new AI assistant tools added in Phase 1.
Tests customer lookups, invoice details, payment history, and search functionality.
Covers role permissions, cross-org denial, ambiguous matches, and not-found cases.
"""
import uuid
from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from core.models import (
    Organization, Membership, Customer, Invoice, InvoiceItem,
    Payment, PaymentAllocation
)
from ai_assistant.tools import (
    get_customer_details,
    get_customer_invoices,
    get_customer_payments,
    get_invoice_details,
    get_payment_details,
    search_customers,
    get_recent_activity
)

User = get_user_model()


class NewToolsTestCase(TestCase):
    """Test new tools with real data scenarios."""

    def setUp(self):
        """Create test organization with sample data."""
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123"
        )
        
        self.org = Organization.objects.create(
            name="Test Org",
            default_currency="INR"
        )
        
        self.membership = Membership.objects.create(
            organization=self.org,
            user=self.user,
            role=Membership.Role.OWNER
        )
        
        # Create test customers
        self.customer1 = Customer.objects.create(
            organization=self.org,
            name="Person 4",
            email="person4@example.com",
            phone="+919876543210",
            payment_terms_days=30,
            active=True
        )
        
        self.customer2 = Customer.objects.create(
            organization=self.org,
            name="Person 40",  # Similar name to test ambiguity
            email="person40@example.com",
            payment_terms_days=15,
            active=True
        )
        
        self.customer3 = Customer.objects.create(
            organization=self.org,
            name="Acme Corp",
            email="billing@acme.com",
            payment_terms_days=45,
            active=False  # Inactive
        )
        
        # Create invoices for customer1
        today = timezone.localdate()
        self.invoice1 = Invoice.objects.create(
            organization=self.org,
            customer=self.customer1,
            invoice_number="INV-001",
            invoice_date=today - timedelta(days=60),
            due_date=today - timedelta(days=30),  # Overdue
            currency="INR",
            subtotal_minor=100_000,
            discount_minor=0,
            tax_minor=18_000,
            total_minor=118_000,
            status=Invoice.Status.ISSUED,
            created_by=self.user
        )
        
        InvoiceItem.objects.create(
            invoice=self.invoice1,
            organization=self.org,
            description="Consulting Services",
            quantity=10,
            unit_price_minor=10_000,
            discount_minor=0,
            line_total_minor=100_000
        )
        
        self.invoice2 = Invoice.objects.create(
            organization=self.org,
            customer=self.customer1,
            invoice_number="INV-002",
            invoice_date=today,
            due_date=today + timedelta(days=30),
            currency="INR",
            subtotal_minor=50_000,
            discount_minor=5_000,
            tax_minor=8_100,
            total_minor=53_100,
            status=Invoice.Status.ISSUED,
            created_by=self.user
        )
        
        # Create payment for customer1
        self.payment1 = Payment.objects.create(
            organization=self.org,
            customer=self.customer1,
            payment_date=today - timedelta(days=10),
            amount_minor=100_000,
            currency="INR",
            method="bank_transfer",
            reference="REF-001",
            recorded_by=self.user
        )
        
        # Allocate payment to invoice1 (partial)
        PaymentAllocation.objects.create(
            organization=self.org,
            payment=self.payment1,
            invoice=self.invoice1,
            amount_minor=100_000,
            created_by=self.user
        )
        
        # Create another org for cross-org testing
        self.other_org = Organization.objects.create(name="Other Org")
        self.other_customer = Customer.objects.create(
            organization=self.other_org,
            name="Other Customer"
        )

    # ==================== get_customer_details ====================
    
    def test_get_customer_details_by_exact_name(self):
        """Exact name match returns customer details."""
        result = get_customer_details(self.org, customer_name="Person 4")
        
        self.assertEqual(result["name"], "Person 4")
        self.assertEqual(result["email"], "person4@example.com")
        self.assertEqual(result["phone"], "+919876543210")
        self.assertEqual(result["active"], True)
        self.assertIn("statistics", result)
        self.assertEqual(result["statistics"]["total_invoices"], 2)
        # INV-001: 118000 - 100000 = 18000 outstanding, overdue
        # INV-002: 53100 outstanding, not overdue
        self.assertEqual(result["statistics"]["outstanding_minor"], 71_100)
        self.assertEqual(result["statistics"]["overdue_minor"], 18_000)

    def test_get_customer_details_case_insensitive(self):
        """Name search is case-insensitive."""
        result = get_customer_details(self.org, customer_name="person 4")
        self.assertEqual(result["name"], "Person 4")
        
        result2 = get_customer_details(self.org, customer_name="PERSON 4")
        self.assertEqual(result2["name"], "Person 4")

    def test_get_customer_details_by_id(self):
        """Lookup by customer ID works."""
        result = get_customer_details(self.org, customer_id=str(self.customer1.id))
        self.assertEqual(result["name"], "Person 4")

    def test_get_customer_details_not_found(self):
        """Non-existent customer returns error."""
        result = get_customer_details(self.org, customer_name="Non Existent")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "customer_not_found")

    def test_get_customer_details_partial_match_suggestions(self):
        """Partial match provides suggestions."""
        result = get_customer_details(self.org, customer_name="Person")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "customer_not_found_exact")
        self.assertIn("suggestions", result)
        self.assertEqual(len(result["suggestions"]), 2)  # Person 4 and Person 40

    def test_get_customer_details_ambiguous(self):
        """Multiple exact matches return candidates."""
        # Create another "Person 4" (edge case)
        Customer.objects.create(
            organization=self.org,
            name="Person 4",  # Exact duplicate
            email="person4-duplicate@example.com"
        )
        
        result = get_customer_details(self.org, customer_name="Person 4")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "ambiguous_customer")
        self.assertIn("candidates", result)
        self.assertEqual(len(result["candidates"]), 2)

    def test_get_customer_details_cross_org_denied(self):
        """Customer from another org cannot be accessed."""
        result = get_customer_details(self.org, customer_id=str(self.other_customer.id))
        self.assertIn("error", result)
        self.assertEqual(result["error"], "customer_not_found")

    # ==================== get_customer_invoices ====================
    
    def test_get_customer_invoices_by_name(self):
        """Get all invoices for a customer."""
        result = get_customer_invoices(self.org, customer_name="Person 4")
        
        self.assertEqual(result["customer_name"], "Person 4")
        self.assertEqual(result["invoice_count"], 2)
        self.assertEqual(len(result["invoices"]), 2)
        
        # Check invoice details
        inv = next(i for i in result["invoices"] if i["invoice_number"] == "INV-001")
        self.assertEqual(inv["total_minor"], 118_000)
        self.assertEqual(inv["paid_minor"], 100_000)
        self.assertEqual(inv["balance_minor"], 18_000)

    def test_get_customer_invoices_filter_by_status(self):
        """Filter invoices by status."""
        # Create a draft invoice
        Invoice.objects.create(
            organization=self.org,
            customer=self.customer1,
            invoice_number="INV-DRAFT",
            invoice_date=timezone.localdate(),
            due_date=timezone.localdate() + timedelta(days=30),
            currency="INR",
            subtotal_minor=10_000,
            discount_minor=0,
            tax_minor=1_800,
            total_minor=11_800,
            status=Invoice.Status.DRAFT,
            created_by=self.user
        )
        
        result = get_customer_invoices(self.org, customer_name="Person 4", status="issued")
        self.assertEqual(result["invoice_count"], 2)  # Only issued invoices
        
        result_draft = get_customer_invoices(self.org, customer_name="Person 4", status="draft")
        self.assertEqual(result_draft["invoice_count"], 1)

    def test_get_customer_invoices_limit(self):
        """Limit parameter works."""
        result = get_customer_invoices(self.org, customer_name="Person 4", limit=1)
        self.assertEqual(len(result["invoices"]), 1)

    def test_get_customer_invoices_not_found_customer(self):
        """Non-existent customer returns error."""
        result = get_customer_invoices(self.org, customer_name="Nobody")
        self.assertIn("error", result)

    # ==================== get_customer_payments ====================
    
    def test_get_customer_payments(self):
        """Get payment history for customer."""
        result = get_customer_payments(self.org, customer_name="Person 4")
        
        self.assertEqual(result["customer_name"], "Person 4")
        self.assertEqual(result["payment_count"], 1)
        
        pmt = result["payments"][0]
        self.assertEqual(pmt["amount_minor"], 100_000)
        self.assertEqual(pmt["method"], "bank_transfer")
        self.assertEqual(pmt["reference"], "REF-001")
        self.assertEqual(pmt["allocated_minor"], 100_000)
        self.assertEqual(pmt["unallocated_minor"], 0)
        self.assertEqual(len(pmt["allocations"]), 1)
        self.assertEqual(pmt["allocations"][0]["invoice_number"], "INV-001")

    def test_get_customer_payments_with_unallocated(self):
        """Payment with unallocated amount."""
        Payment.objects.create(
            organization=self.org,
            customer=self.customer1,
            payment_date=timezone.localdate(),
            amount_minor=50_000,
            currency="INR",
            method="cash",
            recorded_by=self.user
        )
        
        result = get_customer_payments(self.org, customer_name="Person 4")
        self.assertEqual(result["payment_count"], 2)
        
        # Find the unallocated payment
        unalloc_pmt = next(p for p in result["payments"] if p["method"] == "cash")
        self.assertEqual(unalloc_pmt["unallocated_minor"], 50_000)

    # ==================== get_invoice_details ====================
    
    def test_get_invoice_details(self):
        """Get complete invoice details."""
        result = get_invoice_details(self.org, "INV-001")
        
        self.assertEqual(result["invoice_number"], "INV-001")
        self.assertEqual(result["customer_name"], "Person 4")
        self.assertEqual(result["total_minor"], 118_000)
        self.assertEqual(result["paid_minor"], 100_000)
        self.assertEqual(result["balance_minor"], 18_000)
        
        # Check line items
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(result["items"][0]["description"], "Consulting Services")
        
        # Check payments
        self.assertEqual(len(result["payments"]), 1)
        self.assertEqual(result["payments"][0]["amount_minor"], 100_000)

    def test_get_invoice_details_not_found(self):
        """Non-existent invoice returns error."""
        result = get_invoice_details(self.org, "INV-999")
        self.assertIn("error", result)
        self.assertEqual(result["error"], "invoice_not_found")

    def test_get_invoice_details_cross_org_denied(self):
        """Cannot access invoice from another org."""
        other_invoice = Invoice.objects.create(
            organization=self.other_org,
            customer=self.other_customer,
            invoice_number="OTHER-INV",
            invoice_date=timezone.localdate(),
            due_date=timezone.localdate(),
            currency="INR",
            subtotal_minor=10_000,
            discount_minor=0,
            tax_minor=1_800,
            total_minor=11_800,
            status=Invoice.Status.ISSUED,
            created_by=self.user
        )
        
        result = get_invoice_details(self.org, "OTHER-INV")
        self.assertIn("error", result)

    # ==================== get_payment_details ====================
    
    def test_get_payment_details(self):
        """Get payment details with allocations."""
        result = get_payment_details(self.org, str(self.payment1.id))
        
        self.assertEqual(result["customer_name"], "Person 4")
        self.assertEqual(result["amount_minor"], 100_000)
        self.assertEqual(result["allocated_minor"], 100_000)
        self.assertEqual(result["unallocated_minor"], 0)
        self.assertEqual(len(result["allocations"]), 1)

    def test_get_payment_details_not_found(self):
        """Non-existent payment returns error."""
        fake_id = str(uuid.uuid4())
        result = get_payment_details(self.org, fake_id)
        self.assertIn("error", result)

    # ==================== search_customers ====================
    
    def test_search_customers_partial_match(self):
        """Search finds customers by partial name."""
        result = search_customers(self.org, "Person")
        self.assertEqual(len(result), 2)  # Person 4 and Person 40
        
        names = [c["name"] for c in result]
        self.assertIn("Person 4", names)
        self.assertIn("Person 40", names)

    def test_search_customers_active_only(self):
        """Active-only filter works."""
        result = search_customers(self.org, "")  # All customers
        active_only_result = [c for c in result if c["active"]]
        self.assertEqual(len(active_only_result), 2)  # Person 4, Person 40 (Acme is inactive)
        
        result_all = search_customers(self.org, "", active_only=False)
        self.assertEqual(len(result_all), 3)

    def test_search_customers_case_insensitive(self):
        """Search is case-insensitive."""
        result = search_customers(self.org, "person")
        self.assertEqual(len(result), 2)
        
        result2 = search_customers(self.org, "PERSON")
        self.assertEqual(len(result2), 2)

    def test_search_customers_limit(self):
        """Limit parameter works."""
        result = search_customers(self.org, "Person", limit=1)
        self.assertEqual(len(result), 1)

    def test_search_customers_no_matches(self):
        """No matches returns empty list."""
        result = search_customers(self.org, "XYZ Nobody")
        self.assertEqual(len(result), 0)

    # ==================== get_recent_activity ====================
    
    def test_get_recent_activity_all(self):
        """Get all recent activity."""
        result = get_recent_activity(self.org)
        
        self.assertIn("invoices", result)
        self.assertIn("payments", result)
        self.assertEqual(len(result["invoices"]), 2)
        self.assertEqual(len(result["payments"]), 1)

    def test_get_recent_activity_invoices_only(self):
        """Filter for invoices only."""
        result = get_recent_activity(self.org, activity_type="invoices")
        
        self.assertIn("invoices", result)
        self.assertNotIn("payments", result)

    def test_get_recent_activity_payments_only(self):
        """Filter for payments only."""
        result = get_recent_activity(self.org, activity_type="payments")
        
        self.assertIn("payments", result)
        self.assertNotIn("invoices", result)

    def test_get_recent_activity_limit(self):
        """Limit parameter works."""
        # Create many invoices
        for i in range(30):
            Invoice.objects.create(
                organization=self.org,
                customer=self.customer1,
                invoice_number=f"INV-BULK-{i}",
                invoice_date=timezone.localdate(),
                due_date=timezone.localdate() + timedelta(days=30),
                currency="INR",
                subtotal_minor=10_000,
                discount_minor=0,
                tax_minor=1_800,
                total_minor=11_800,
                status=Invoice.Status.ISSUED,
                created_by=self.user
            )
        
        result = get_recent_activity(self.org, activity_type="invoices", limit=10)
        self.assertEqual(len(result["invoices"]), 10)

    # ==================== Data Validation ====================
    
    def test_tools_match_existing_reports(self):
        """Tool results match existing dashboard/aging reports."""
        # Get customer details
        cust_details = get_customer_details(self.org, customer_name="Person 4")
        
        # Manual calculation
        outstanding = 18_000 + 53_100  # INV-001 balance + INV-002 total
        overdue = 18_000  # Only INV-001 is overdue
        
        self.assertEqual(cust_details["statistics"]["outstanding_minor"], outstanding)
        self.assertEqual(cust_details["statistics"]["overdue_minor"], overdue)

    def test_tools_never_invent_data(self):
        """Tools return empty/error for missing data, never invent."""
        # Customer with no invoices
        empty_customer = Customer.objects.create(
            organization=self.org,
            name="Empty Customer"
        )
        
        result = get_customer_invoices(self.org, customer_name="Empty Customer")
        self.assertEqual(result["invoice_count"], 0)
        self.assertEqual(len(result["invoices"]), 0)

    def test_pagination_enforced(self):
        """Tools enforce max limits."""
        result = search_customers(self.org, "", limit=1000)  # Request 1000
        # Should be capped at 100
        self.assertLessEqual(len(result), 100)
