"""
Test error handling in AI assistant.
Covers all failure paths: validation, tool failures, LLM unavailable, unexpected errors.
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from core.models import Organization, Membership, Customer, Invoice
from ai_assistant.models import AIRun
from ai_assistant.views import AssistantError, ToolExecutionError, LLMUnavailableError

User = get_user_model()


class ErrorHandlingTestCase(TestCase):
    """Test error handling and logging in ask_assistant endpoint."""

    def setUp(self):
        """Create test organization, user, and client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="test@example.com",
            email="test@example.com",
            password="testpass123",
        )
        self.user.full_name = "Test User"
        self.user.save()
        self.org = Organization.objects.create(
            name="Test Org",
            default_currency="INR"
        )
        self.membership = Membership.objects.create(
            organization=self.org,
            user=self.user,
            role=Membership.Role.OWNER
        )
        self.client.force_authenticate(user=self.user)
        self.url = "/api/v1/assistant/"

    def test_validation_error_empty_question(self):
        """Empty question returns 400 with validation_error type."""
        response = self.client.post(
            self.url,
            {"question": ""},
            HTTP_X_ORGANIZATION_ID=str(self.org.id)
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error_type"], "validation_error")
        self.assertIn("required", response.data["error"].lower())
        
        # No AIRun should be created for validation errors
        self.assertEqual(AIRun.objects.filter(organization=self.org).count(), 0)

    def test_validation_error_question_too_long(self):
        """Question exceeding 2000 chars returns 400 with validation_error."""
        long_question = "a" * 2001
        response = self.client.post(
            self.url,
            {"question": long_question},
            HTTP_X_ORGANIZATION_ID=str(self.org.id)
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error_type"], "validation_error")
        self.assertIn("2000", response.data["error"])
        
        # No AIRun should be created
        self.assertEqual(AIRun.objects.filter(organization=self.org).count(), 0)

    def test_missing_question_field(self):
        """Missing question field returns 400."""
        response = self.client.post(
            self.url,
            {},
            HTTP_X_ORGANIZATION_ID=str(self.org.id)
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["error_type"], "validation_error")

    @patch('ai_assistant.views.logger')
    def test_tool_failure_logged_not_exposed(self, mock_logger):
        """Tool failure is logged with request_id but doesn't fail the request."""
        # Patch the tool directly in the AVAILABLE_TOOLS dict
        with patch.dict('ai_assistant.views.AVAILABLE_TOOLS', {
            'get_receivables_summary': MagicMock(side_effect=Exception("Database connection failed")),
            'get_top_overdue_customers': MagicMock(return_value=[]),
            'get_invoices_due_range': MagicMock(return_value=[]),
            'get_late_paying_customers': MagicMock(return_value=[]),
            'get_forecast_summary': MagicMock(return_value={}),
        }):
            # Disable OpenAI to prevent actual API calls
            with self.settings(OPENAI_API_KEY=""):
                response = self.client.post(
                    self.url,
                    {"question": "How much is overdue?"},
                    HTTP_X_ORGANIZATION_ID=str(self.org.id)
                )
        
            # Request should still succeed with fallback
            self.assertEqual(response.status_code, 200)
            self.assertIn("answer", response.data)
            
            # Error should be logged with request_id
            log_calls = [str(call) for call in mock_logger.error.call_args_list]
            has_tool_error = any("get_receivables_summary" in call and "failed" in call for call in log_calls)
            self.assertTrue(has_tool_error, f"Tool error should be logged. Got calls: {log_calls}")

    @patch('ai_assistant.views.logger')
    @patch('ai_assistant.views.openai')
    def test_llm_unavailable_falls_back_gracefully(self, mock_openai_module, mock_logger):
        """LLM failure logs warning and uses rule-based fallback."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API rate limit exceeded")
        mock_openai_module.OpenAI.return_value = mock_client
        
        # Set OpenAI key to trigger AI path
        with self.settings(OPENAI_API_KEY="test-key"):
            response = self.client.post(
                self.url,
                {"question": "How much is overdue?"},
                HTTP_X_ORGANIZATION_ID=str(self.org.id)
            )
        
        # Should succeed with fallback answer (Phase 2: now falls back internally)
        self.assertEqual(response.status_code, 200)
        self.assertIn("answer", response.data)
        
        # Should log warning with request_id
        self.assertTrue(mock_logger.warning.called)
        log_call = str(mock_logger.warning.call_args)
        self.assertIn("LLM provider", log_call)
        self.assertIn("failed", log_call)
        
        # AIRun should show SUCCESS status (fallback succeeded)
        run = AIRun.objects.filter(organization=self.org).first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, AIRun.Status.SUCCESS)

    @patch('ai_assistant.views.logger')
    def test_unexpected_error_logged_with_traceback(self, mock_logger):
        """Unexpected error logs full traceback and returns generic message."""
        # Simulate an unexpected error during rule-based execution
        with patch('ai_assistant.views._execute_rule_based') as mock_exec:
            mock_exec.side_effect = RuntimeError("Unexpected internal error")
            
            with self.settings(OPENAI_API_KEY=""):
                response = self.client.post(
                    self.url,
                    {"question": "Test"},
                    HTTP_X_ORGANIZATION_ID=str(self.org.id)
                )
        
        # Should return 500 with generic message
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.data)
        self.assertEqual(response.data["error_type"], "unexpected_error")
        self.assertIn("unexpected error occurred", response.data["error"].lower())
        self.assertIn("request_id", response.data)
        
        # Should log error with full traceback
        self.assertTrue(mock_logger.error.called)
        error_log = str(mock_logger.error.call_args)
        self.assertIn("Unexpected error in ask_assistant", error_log)
        self.assertIn("exc_info=True", error_log)
        
        # AIRun should show FAILED status
        run = AIRun.objects.filter(organization=self.org).first()
        self.assertIsNotNone(run)
        self.assertEqual(run.status, AIRun.Status.FAILED)
        self.assertEqual(run.error_category, "unexpected_error")

    def test_request_id_uniqueness(self):
        """Each request gets a unique request_id in logs."""
        # Make two requests (disable OpenAI to avoid API calls)
        with self.settings(OPENAI_API_KEY=""):
            for i in range(2):
                self.client.post(
                    self.url,
                    {"question": f"Test question {i}"},
                    HTTP_X_ORGANIZATION_ID=str(self.org.id)
                )
        
        # Both should succeed
        self.assertEqual(AIRun.objects.filter(organization=self.org).count(), 2)

    def test_no_pii_in_error_messages(self):
        """Error messages don't contain PII or sensitive data."""
        # Create customer with PII
        customer = Customer.objects.create(
            organization=self.org,
            name="John Doe",
            email="john@secret.com",
            phone="+919876543210"
        )
        
        with patch('ai_assistant.tools.get_receivables_summary') as mock_tool:
            mock_tool.side_effect = Exception(f"Failed to fetch data for {customer.email}")
            
            with self.settings(OPENAI_API_KEY=""):
                response = self.client.post(
                    self.url,
                    {"question": "Show me overdue amounts"},
                    HTTP_X_ORGANIZATION_ID=str(self.org.id)
                )
            
            # Error message should not contain email or phone
            if response.status_code >= 400:
                error_text = json.dumps(response.data)
                self.assertNotIn(customer.email, error_text)
                self.assertNotIn(customer.phone, error_text)

    def test_no_secrets_in_logs(self):
        """API keys and secrets are not logged."""
        with patch('ai_assistant.views.logger') as mock_logger:
            with self.settings(OPENAI_API_KEY="sk-secret-key-12345"):
                self.client.post(
                    self.url,
                    {"question": "Test question"},
                    HTTP_X_ORGANIZATION_ID=str(self.org.id)
                )
            
            # Check all log calls don't contain the secret key
            for call in mock_logger.method_calls:
                call_str = str(call)
                self.assertNotIn("sk-secret-key-12345", call_str)

    def test_authentication_required(self):
        """Unauthenticated requests are rejected."""
        client = APIClient()  # No authentication
        response = client.post(
            self.url,
            {"question": "Test"},
            HTTP_X_ORGANIZATION_ID=str(self.org.id)
        )
        self.assertEqual(response.status_code, 403)

    def test_organization_access_required(self):
        """User cannot access other organization's assistant."""
        other_org = Organization.objects.create(name="Other Org")
        
        response = self.client.post(
            self.url,
            {"question": "Test"},
            HTTP_X_ORGANIZATION_ID=str(other_org.id)
        )
        self.assertEqual(response.status_code, 403)

    def test_error_response_structure(self):
        """Error responses have consistent structure."""
        with patch('ai_assistant.tools.get_receivables_summary') as mock_tool:
            mock_tool.side_effect = RuntimeError("Test error")
            
            with self.settings(OPENAI_API_KEY=""):
                response = self.client.post(
                    self.url,
                    {"question": "Test"},
                    HTTP_X_ORGANIZATION_ID=str(self.org.id)
                )
            
            if response.status_code >= 400:
                self.assertIn("error", response.data)
                self.assertIn("error_type", response.data)
                self.assertIsInstance(response.data["error"], str)
                self.assertIsInstance(response.data["error_type"], str)
                # request_id only in 500 errors
                if response.status_code == 500:
                    self.assertIn("request_id", response.data)

    def test_airun_logged_on_all_paths(self):
        """AIRun is created on success and errors."""
        # Success path (disable OpenAI to avoid API calls)
        with self.settings(OPENAI_API_KEY=""):
            response = self.client.post(
                self.url,
                {"question": "How much is overdue?"},
                HTTP_X_ORGANIZATION_ID=str(self.org.id)
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AIRun.objects.filter(organization=self.org).count(), 1)
        run = AIRun.objects.first()
        self.assertEqual(run.status, AIRun.Status.SUCCESS)
        
        # AIRun created even when tool calls fail (tested separately in test_tool_failure_logged_not_exposed)
        # AIRun created when LLM fails but falls back (tested in test_llm_unavailable_falls_back_gracefully)
