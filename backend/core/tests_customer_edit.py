"""
Tests for Customer Edit functionality
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from core.models import Organization, Membership, Customer

User = get_user_model()


class CustomerEditTestCase(TestCase):
    """Test customer editing endpoint, permissions, and validation"""

    def setUp(self):
        # Create test organization and users
        self.org = Organization.objects.create(name="Test Org", state="07")  # Delhi
        
        self.owner = User.objects.create_user(username="owner@test.com", email="owner@test.com", password="pass")
        self.manager = User.objects.create_user(username="manager@test.com", email="manager@test.com", password="pass")
        self.viewer = User.objects.create_user(username="viewer@test.com", email="viewer@test.com", password="pass")
        self.collector = User.objects.create_user(username="collector@test.com", email="collector@test.com", password="pass")
        
        Membership.objects.create(organization=self.org, user=self.owner, role=Membership.Role.OWNER)
        Membership.objects.create(organization=self.org, user=self.manager, role=Membership.Role.MANAGER)
        Membership.objects.create(organization=self.org, user=self.viewer, role=Membership.Role.VIEWER)
        Membership.objects.create(organization=self.org, user=self.collector, role=Membership.Role.COLLECTOR)
        
        # Create a test customer
        self.customer = Customer.objects.create(
            organization=self.org,
            name="Test Customer",
            email="test@customer.com",
            phone="+91 98765 43210",
            billing_address="123 Test St",
            gstin="07AAAAA0000A1Z5",
            state="07",
            payment_terms_days=30,
            notes="Original notes",
            active=True,
        )
        
        self.client = APIClient()

    def test_owner_can_edit_customer(self):
        """Owner role can edit customer details"""
        self.client.force_authenticate(user=self.owner)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {
                "name": "Updated Customer Name",
                "email": "updated@customer.com",
                "phone": "+91 99999 88888",
            },
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Updated Customer Name")
        self.assertEqual(self.customer.email, "updated@customer.com")

    def test_manager_can_edit_customer(self):
        """Manager role can edit customer details"""
        self.client.force_authenticate(user=self.manager)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {"name": "Manager Updated"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, "Manager Updated")

    def test_viewer_cannot_edit_customer(self):
        """Viewer role cannot edit customers"""
        self.client.force_authenticate(user=self.viewer)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {"name": "Should Fail"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 403)

    def test_collector_cannot_edit_customer(self):
        """Collector role cannot edit customers"""
        self.client.force_authenticate(user=self.collector)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {"name": "Should Fail"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 403)

    def test_cannot_edit_customer_from_different_org(self):
        """Users cannot edit customers from different organizations"""
        other_org = Organization.objects.create(name="Other Org")
        other_customer = Customer.objects.create(
            organization=other_org,
            name="Other Customer",
            email="other@customer.com",
        )
        
        self.client.force_authenticate(user=self.owner)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        response = self.client.patch(
            f"/api/v1/customers/{other_customer.id}/",
            {"name": "Should Fail"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 404)

    def test_deactivate_customer(self):
        """Deactivating a customer keeps all data intact"""
        self.client.force_authenticate(user=self.owner)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {"active": False},
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.active)
        # All other fields should remain unchanged
        self.assertEqual(self.customer.name, "Test Customer")
        self.assertEqual(self.customer.email, "test@customer.com")

    def test_duplicate_customer_warning(self):
        """Editing to duplicate details shows warning"""
        # Create another customer
        other_customer = Customer.objects.create(
            organization=self.org,
            name="Other Customer",
            email="other@customer.com",
        )
        
        self.client.force_authenticate(user=self.owner)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        # Try to change first customer's email to match the second
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {"email": "other@customer.com"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        # Should include a warning
        self.assertIn("warnings", response.data)
        self.assertTrue(any("email" in str(w).lower() for w in response.data["warnings"]))

    def test_duplicate_warning_excludes_current_customer(self):
        """Duplicate check excludes the customer being edited"""
        self.client.force_authenticate(user=self.owner)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        # Update customer with its own email - should NOT warn
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {"email": "test@customer.com", "name": "Updated Name"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        # Should not include warnings since we're using the same email
        self.assertNotIn("warnings", response.data)

    def test_gstin_validation(self):
        """GSTIN format is validated"""
        self.client.force_authenticate(user=self.owner)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {"gstin": "INVALID"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("gstin", str(response.data).lower())

    def test_edit_creates_audit_log(self):
        """Editing a customer creates an audit log entry"""
        from core.models import AuditLog
        
        self.client.force_authenticate(user=self.owner)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        initial_count = AuditLog.objects.count()
        
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {"name": "Audit Test Customer", "email": "audit@test.com"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AuditLog.objects.count(), initial_count + 1)
        
        log_entry = AuditLog.objects.latest("created_at")
        self.assertEqual(log_entry.action, "customer.updated")
        self.assertEqual(log_entry.entity_type, "customer")
        self.assertEqual(log_entry.entity_id, str(self.customer.id))
        self.assertEqual(log_entry.actor, self.owner)
        # Summary should include what changed
        self.assertIn("name", log_entry.summary)

    def test_edit_preserves_related_data(self):
        """Editing customer doesn't affect related invoices or payments"""
        from core.models import Invoice, Payment
        
        # Create related data
        invoice = Invoice.objects.create(
            organization=self.org,
            customer=self.customer,
            invoice_number="INV-001",
            invoice_date="2024-01-01",
            due_date="2024-01-31",
            subtotal_minor=100000,
            total_minor=100000,
            status=Invoice.Status.ISSUED,
            created_by=self.owner,
        )
        
        payment = Payment.objects.create(
            organization=self.org,
            customer=self.customer,
            payment_date="2024-01-15",
            amount_minor=50000,
            recorded_by=self.owner,
        )
        
        self.client.force_authenticate(user=self.owner)
        self.client.credentials(HTTP_X_ORGANIZATION_ID=str(self.org.id))
        
        # Edit customer
        response = self.client.patch(
            f"/api/v1/customers/{self.customer.id}/",
            {"name": "New Name", "email": "new@email.com"},
            format="json",
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Related objects should still exist and point to the customer
        invoice.refresh_from_db()
        payment.refresh_from_db()
        self.assertEqual(invoice.customer_id, self.customer.id)
        self.assertEqual(payment.customer_id, self.customer.id)
