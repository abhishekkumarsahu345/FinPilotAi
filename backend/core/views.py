from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model, login, logout, password_validation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie

from rest_framework import serializers as drf_serializers, viewsets, permissions, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response

from .models import (
    Organization, Membership, Customer, Invoice, Payment, PaymentAllocation, AuditLog,
)
from .permissions import HasOrganizationAccess, WRITE_ROLES
from .serializers import (
    OrganizationSerializer, MembershipSerializer, CustomerSerializer,
    InvoiceSerializer, PaymentSerializer, AuditSerializer,
)

User = get_user_model()


# ---------------------------------------------------------------------------
# Organization-scoped mixin
# ---------------------------------------------------------------------------

class OrgScopedMixin:
    """Provides organization-scoped queryset and permission enforcement."""
    permission_classes = [permissions.IsAuthenticated, HasOrganizationAccess]

    def get_org(self):
        return self.request.membership.organization


# ---------------------------------------------------------------------------
# ViewSets
# ---------------------------------------------------------------------------

class OrganizationViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_queryset(self):
        return Organization.objects.filter(
            memberships__user=self.request.user,
            memberships__active=True,
        )

    def create(self, request, *args, **kwargs):
        # Override to not require X-Organization-ID for new org creation
        serializer = OrganizationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        org = serializer.save()
        return Response(
            OrganizationSerializer(org, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def get_permissions(self):
        if self.action == "create":
            return [permissions.IsAuthenticated()]
        return super().get_permissions()


class CustomerViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    serializer_class = CustomerSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    search_fields = ["name", "email", "phone", "gstin"]
    ordering_fields = ["name", "created_at"]
    filterset_fields = {"active": ["exact"]}

    def get_queryset(self):
        return Customer.objects.filter(organization=self.get_org())

    def perform_create(self, serializer):
        warnings = serializer.validated_data.pop("_warnings", [])
        customer = serializer.save()
        AuditLog.objects.create(
            organization=customer.organization,
            actor=self.request.user,
            action="customer.created",
            entity_type="customer",
            entity_id=str(customer.id),
            summary=f"Created customer {customer.name}",
        )
        # Store warnings on the serializer for to_response use
        self._create_warnings = warnings

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        warnings = serializer.validated_data.pop("_warnings", [])
        self.perform_create(serializer)
        data = serializer.data
        if warnings:
            data["warnings"] = warnings
        return Response(data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        warnings = serializer.validated_data.pop("_warnings", [])
        # Capture old values for audit log
        instance = self.get_object()
        old_values = {
            'name': instance.name,
            'email': instance.email,
            'phone': instance.phone,
            'active': instance.active,
        }
        customer = serializer.save()
        # Build change summary
        changes = []
        if old_values['name'] != customer.name:
            changes.append(f"name: '{old_values['name']}' → '{customer.name}'")
        if old_values['email'] != customer.email:
            changes.append(f"email: '{old_values['email']}' → '{customer.email}'")
        if old_values['phone'] != customer.phone:
            changes.append(f"phone: '{old_values['phone']}' → '{customer.phone}'")
        if old_values['active'] != customer.active:
            status = 'activated' if customer.active else 'deactivated'
            changes.append(f"status: {status}")
        summary = f"Updated customer {customer.name}" + (f" ({', '.join(changes)})" if changes else "")
        AuditLog.objects.create(
            organization=customer.organization,
            actor=self.request.user,
            action="customer.updated",
            entity_type="customer",
            entity_id=str(customer.id),
            summary=summary[:500],  # Respect max_length
        )
        # Store warnings for response
        self._update_warnings = warnings

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        data = serializer.data
        if hasattr(self, '_update_warnings') and self._update_warnings:
            data['warnings'] = self._update_warnings
        return Response(data)

    @action(detail=True, methods=["post"])
    def opt_out(self, request, pk=None):
        customer = self.get_object()
        with transaction.atomic():
            customer.opt_out = True
            customer.opt_out_recorded_at = timezone.now()
            customer.save()
            AuditLog.objects.create(
                organization=customer.organization,
                actor=request.user,
                action="customer.opt_out",
                entity_type="customer",
                entity_id=str(customer.id),
                summary=f"Customer {customer.name} opted out of reminders",
            )
        return Response({"detail": "Customer has been opted out of reminders."})

    @action(detail=True, methods=["post"])
    def opt_in(self, request, pk=None):
        customer = self.get_object()
        with transaction.atomic():
            customer.opt_out = False
            customer.opt_out_recorded_at = None
            customer.save()
            AuditLog.objects.create(
                organization=customer.organization,
                actor=request.user,
                action="customer.opt_in",
                entity_type="customer",
                entity_id=str(customer.id),
                summary=f"Customer {customer.name} opted back into reminders",
            )
        return Response({"detail": "Customer has been opted back in."})


class InvoiceViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    serializer_class = InvoiceSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]
    search_fields = ["invoice_number", "customer__name"]
    filterset_fields = {"status": ["exact"], "customer": ["exact"]}
    ordering_fields = ["invoice_date", "due_date", "total_minor", "created_at"]

    def get_queryset(self):
        return (
            Invoice.objects.filter(organization=self.get_org())
            .select_related("customer")
            .prefetch_related("allocations", "items")
        )

    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        invoice = self.get_object()
        if invoice.status == Invoice.Status.VOID:
            return Response({"detail": "Invoice is already void."})
        active_allocs = invoice.allocations.filter(reversed_at__isnull=True)
        if active_allocs.exists():
            return Response(
                {"detail": "Reverse existing allocations before voiding this invoice."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            invoice.status = Invoice.Status.VOID
            invoice.updated_by = request.user
            invoice.save()
            AuditLog.objects.create(
                organization=invoice.organization,
                actor=request.user,
                action="invoice.voided",
                entity_type="invoice",
                entity_id=str(invoice.id),
                summary=f"Voided invoice {invoice.invoice_number}",
            )
        return Response(InvoiceSerializer(invoice, context={"request": request}).data)


class PaymentViewSet(OrgScopedMixin, viewsets.ModelViewSet):
    serializer_class = PaymentSerializer
    http_method_names = ["get", "post", "head", "options"]
    ordering_fields = ["payment_date", "amount_minor", "created_at"]
    filterset_fields = {"customer": ["exact"], "status": ["exact"]}

    def get_queryset(self):
        return (
            Payment.objects.filter(organization=self.get_org())
            .select_related("customer")
            .prefetch_related("allocations__invoice")
            .order_by("-payment_date")
        )

    @action(detail=True, methods=["post"], url_path="allocations/(?P<alloc_id>[^/.]+)/reverse")
    def reverse_allocation(self, request, pk=None, alloc_id=None):
        payment = self.get_object()
        try:
            alloc = PaymentAllocation.objects.get(
                id=alloc_id,
                payment=payment,
                organization=self.get_org(),
            )
        except PaymentAllocation.DoesNotExist:
            return Response({"detail": "Allocation not found."}, status=status.HTTP_404_NOT_FOUND)
        if alloc.reversed_at:
            return Response({"detail": "Allocation is already reversed."}, status=status.HTTP_400_BAD_REQUEST)
        with transaction.atomic():
            alloc.reversed_at = timezone.now()
            alloc.reversed_by = request.user
            alloc.save()
            AuditLog.objects.create(
                organization=payment.organization,
                actor=request.user,
                action="allocation.reversed",
                entity_type="payment_allocation",
                entity_id=str(alloc.id),
                summary=(
                    f"Reversed allocation of ₹{alloc.amount_minor / 100:.2f} "
                    f"from payment {payment.id} to invoice {alloc.invoice.invoice_number}"
                ),
            )
        return Response({"detail": "Allocation reversed successfully."})


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def dashboard(request):
    org = request.membership.organization
    today = timezone.localdate()

    # Default to current calendar month for "collected" calculation
    period_start = today.replace(day=1)

    invoices = (
        Invoice.objects.filter(organization=org, status=Invoice.Status.ISSUED)
        .prefetch_related("allocations", "customer")
    )

    rows = []  # (invoice, balance)
    for inv in invoices:
        balance = max(
            0,
            inv.total_minor - sum(
                a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
            ),
        )
        if balance:
            rows.append((inv, balance))

    # Top overdue customers (top 10)
    from collections import defaultdict
    cust_overdue = defaultdict(lambda: {"name": "", "overdue_minor": 0, "invoice_count": 0})
    for inv, bal in rows:
        if inv.due_date < today:
            cust_overdue[str(inv.customer_id)]["name"] = inv.customer.name
            cust_overdue[str(inv.customer_id)]["overdue_minor"] += bal
            cust_overdue[str(inv.customer_id)]["invoice_count"] += 1

    top_overdue = sorted(
        [{"customer_id": k, **v} for k, v in cust_overdue.items()],
        key=lambda x: x["overdue_minor"],
        reverse=True,
    )[:10]

    # Recent payments (last 30 days)
    recent_payments = Payment.objects.filter(
        organization=org,
        payment_date__gte=today - timedelta(days=30),
    ).select_related("customer").order_by("-payment_date")[:20]

    collected_month = sum(
        a.amount_minor
        for p in Payment.objects.filter(
            organization=org,
            payment_date__gte=period_start,
        ).prefetch_related("allocations")
        for a in p.allocations.all()
        if a.reversed_at is None
    )

    return Response({
        "currency": org.default_currency,
        "as_of": str(today),
        "reporting_period": f"{period_start} to {today}",
        "outstanding_minor": sum(b for _, b in rows),
        "overdue_minor": sum(b for i, b in rows if i.due_date < today),
        "due_today_minor": sum(b for i, b in rows if i.due_date == today),
        "due_next_7_days_minor": sum(
            b for i, b in rows if today < i.due_date <= today + timedelta(days=7)
        ),
        "collected_this_month_minor": collected_month,
        "overdue_invoice_count": sum(1 for i, _ in rows if i.due_date < today),
        "customer_count": len({i.customer_id for i, _ in rows}),
        "top_overdue_customers": top_overdue,
        "recent_payments": [
            {
                "id": str(p.id),
                "customer_name": p.customer.name,
                "payment_date": str(p.payment_date),
                "amount_minor": p.amount_minor,
                "method": p.method,
            }
            for p in recent_payments
        ],
    })


# ---------------------------------------------------------------------------
# Aging report
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def aging(request):
    org = request.membership.organization
    # Support optional ?as_of=YYYY-MM-DD
    as_of_str = request.query_params.get("as_of")
    if as_of_str:
        try:
            from datetime import date
            today = date.fromisoformat(as_of_str)
        except ValueError:
            return Response(
                {"detail": "Invalid as_of date. Use YYYY-MM-DD format."},
                status=400,
            )
    else:
        today = timezone.localdate()

    invoices = (
        Invoice.objects.filter(organization=org, status=Invoice.Status.ISSUED)
        .select_related("customer")
        .prefetch_related("allocations")
    )

    buckets = {
        "not_yet_due": [],
        "days_1_30": [],
        "days_31_60": [],
        "days_61_90": [],
        "over_90": [],
    }

    for inv in invoices:
        balance = max(
            0,
            inv.total_minor - sum(
                a.amount_minor for a in inv.allocations.all() if a.reversed_at is None
            ),
        )
        if not balance:
            continue
        days = (today - inv.due_date).days
        if days <= 0:
            key = "not_yet_due"
        elif days <= 30:
            key = "days_1_30"
        elif days <= 60:
            key = "days_31_60"
        elif days <= 90:
            key = "days_61_90"
        else:
            key = "over_90"
        buckets[key].append({
            "id": str(inv.id),
            "invoice_number": inv.invoice_number,
            "customer": inv.customer.name,
            "customer_id": str(inv.customer_id),
            "invoice_date": str(inv.invoice_date),
            "due_date": str(inv.due_date),
            "days_overdue": max(0, days),
            "balance_minor": balance,
        })

    # Bucket totals
    totals = {k: sum(r["balance_minor"] for r in v) for k, v in buckets.items()}
    grand_total = sum(totals.values())

    return Response({
        "as_of": str(today),
        "currency": org.default_currency,
        "grand_total_minor": grand_total,
        "bucket_totals": totals,
        "buckets": buckets,
    })


# ---------------------------------------------------------------------------
# Audit logs
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def audit_logs(request):
    qs = AuditLog.objects.filter(
        organization=request.membership.organization
    ).select_related("actor")[:200]
    return Response(AuditSerializer(qs, many=True).data)


# ---------------------------------------------------------------------------
# Team members
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def members_list(request):
    memberships = Membership.objects.filter(
        organization=request.membership.organization
    ).select_related("user")
    return Response(MembershipSerializer(memberships, many=True).data)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def me(request):
    memberships = (
        Membership.objects.filter(user=request.user, active=True)
        .select_related("organization")
    )
    return Response({
        "id": request.user.id,
        "email": request.user.email,
        "full_name": request.user.get_full_name() or request.user.username,
        "organizations": [
            {
                "id": str(m.organization_id),
                "name": m.organization.name,
                "role": m.role,
                "currency": m.organization.default_currency,
            }
            for m in memberships
        ],
    })


@ensure_csrf_cookie
def csrf(request):
    request.META["CSRF_COOKIE_NEEDS_UPDATE"] = True
    return JsonResponse({"detail": "CSRF cookie set"})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def sign_in(request):
    payload = request.data
    username = payload.get("username", "").strip().lower()
    password = payload.get("password", "")

    # Check by email (username field holds email)
    user = authenticate(request, username=username, password=password)
    if user is None:
        AuditLog.objects.create(
            action="auth.login_failed",
            entity_type="user",
            entity_id=username[:80],
            summary="Failed login attempt",
        )
        return Response(
            {"detail": "Email or password is incorrect."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    login(request, user)
    AuditLog.objects.create(
        actor=user,
        action="auth.login",
        entity_type="user",
        entity_id=str(user.id),
        summary=f"User {user.email} signed in",
    )
    return Response({"detail": "Signed in"})


@api_view(["POST"])
@permission_classes([permissions.AllowAny])
def register(request):
    """
    Register a new user account.
    NOTE: Does NOT create an organization automatically.
    Users must complete organization setup after registration.
    """
    payload = request.data
    email = str(payload.get("email", "")).strip().lower()
    full_name = str(payload.get("full_name", "")).strip()
    # org_name parameter is still accepted for backward compatibility but not used
    password = str(payload.get("password", ""))

    if not email or not full_name or not password:
        return Response(
            {"detail": "Name, email, and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.filter(email__iexact=email).exists():
        return Response(
            {"detail": "An account with this email already exists."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = User(username=email, email=email)
    # Set full name across first/last name fields
    parts = full_name.split(" ", 1)
    user.first_name = parts[0][:150]
    user.last_name = parts[1][:150] if len(parts) > 1 else ""

    try:
        password_validation.validate_password(password, user)
    except ValidationError as exc:
        return Response(
            {"detail": " ".join(exc.messages)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Create user and log them in
    user.set_password(password)
    user.save()
    
    # Log registration
    AuditLog.objects.create(
        actor=user,
        action="auth.register",
        entity_type="user",
        entity_id=str(user.id),
        summary=f"Registered user {user.email}",
    )
    
    # Auto-login the user
    login(request, user)

    return Response(
        {"detail": "Account created. Please complete organization setup."},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def sign_out(request):
    if request.user.is_authenticated:
        import uuid
        request_id = str(uuid.uuid4())
        AuditLog.objects.create(
            actor=request.user,
            action="auth.logout",
            entity_type="user",
            entity_id=str(request.user.id),
            summary=f"User {request.user.email} signed out",
            request_id=request_id,
        )
        logout(request)
        return Response({"detail": "Signed out", "request_id": request_id})
    # Already unauthenticated — idempotent success
    logout(request)
    return Response({"detail": "Signed out"})


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def google_oauth_start(request):
    """
    Step 1: Redirect user to Google's OAuth consent screen.
    Generates a state token for CSRF protection.
    """
    from django.conf import settings
    import secrets
    import urllib.parse
    
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return Response(
            {
                "error": "Google OAuth is not configured",
                "error_type": "google_oauth_not_configured",
                "detail": "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env"
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    
    # Generate and store state for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_initiated_at"] = timezone.now().isoformat()
    
    # Build Google OAuth authorization URL
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return Response({"auth_url": auth_url})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def google_oauth_callback(request):
    """
    Step 2: Handle Google's redirect after user authorization.
    Exchanges the authorization code for tokens, verifies the ID token,
    and creates/authenticates the user.
    """
    from django.conf import settings
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    import requests
    
    # Check for errors from Google
    error = request.GET.get("error")
    if error:
        frontend_url = "http://localhost:5173"
        error_msg = request.GET.get("error_description", "Google authentication failed")
        return JsonResponse(
            {
                "error": error_msg,
                "error_type": "google_oauth_error",
                "redirect_url": f"{frontend_url}?google_error={urllib.parse.quote(error_msg)}"
            },
            status=400
        )
    
    # Verify state (CSRF protection)
    state_from_google = request.GET.get("state", "")
    state_from_session = request.session.get("google_oauth_state", "")
    
    if not state_from_google or state_from_google != state_from_session:
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "Invalid state parameter",
                "error_type": "google_oauth_csrf_error",
                "redirect_url": f"{frontend_url}?google_error=invalid_state"
            },
            status=400
        )
    
    # Clean up state from session
    request.session.pop("google_oauth_state", None)
    request.session.pop("google_oauth_initiated_at", None)
    
    # Get authorization code
    code = request.GET.get("code")
    if not code:
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "No authorization code received",
                "error_type": "google_oauth_no_code",
                "redirect_url": f"{frontend_url}?google_error=no_code"
            },
            status=400
        )
    
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    
    try:
        token_response = requests.post(token_url, data=token_data, timeout=10)
        token_response.raise_for_status()
        tokens = token_response.json()
    except Exception as e:
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": f"Failed to exchange code for tokens: {str(e)}",
                "error_type": "google_oauth_token_exchange_error",
                "redirect_url": f"{frontend_url}?google_error=token_exchange_failed"
            },
            status=400
        )
    
    # Verify ID token
    id_token_str = tokens.get("id_token")
    if not id_token_str:
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "No ID token in response",
                "error_type": "google_oauth_no_id_token",
                "redirect_url": f"{frontend_url}?google_error=no_id_token"
            },
            status=400
        )
    
    try:
        # Verify the ID token with Google's public keys
        # Use clock_skew_in_seconds to handle minor time differences between servers
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=settings.GOOGLE_OAUTH_CLOCK_SKEW_SECONDS
        )
        
        # Verify issuer
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Invalid issuer")
        
        # Extract user info
        google_user_id = idinfo["sub"]
        email = idinfo.get("email", "").lower()
        email_verified = idinfo.get("email_verified", False)
        given_name = idinfo.get("given_name", "")
        family_name = idinfo.get("family_name", "")
        full_name = idinfo.get("name", f"{given_name} {family_name}".strip())
        
        if not email or not email_verified:
            raise ValueError("Email not verified or missing")
        
    except ValueError as e:
        import logging
        logger = logging.getLogger(__name__)
        
        # Log the specific verification failure
        error_msg = str(e)
        logger.error(f"Google OAuth ID token verification failed: {error_msg}")
        
        # Detect clock skew issues and log a helpful warning
        if "too early" in error_msg.lower() or "too late" in error_msg.lower():
            logger.warning(
                "Clock skew detected between server and Google; sync system time. "
                f"Current GOOGLE_OAUTH_CLOCK_SKEW_SECONDS: {settings.GOOGLE_OAUTH_CLOCK_SKEW_SECONDS}"
            )
        
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "ID token verification failed",
                "error_type": "google_oauth_verification_error",
                "redirect_url": f"{frontend_url}?google_error=verification_failed"
            },
            status=400
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Google OAuth token verification exception: {str(e)}")
        
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "ID token verification failed",
                "error_type": "google_oauth_verification_error",
                "redirect_url": f"{frontend_url}?google_error=verification_failed"
            },
            status=400
        )
    
    # Import SocialAccount here to avoid circular import
    from .models import SocialAccount
    
    # Check if this Google account is already linked
    try:
        social_account = SocialAccount.objects.select_related("user").get(
            provider=SocialAccount.Provider.GOOGLE,
            provider_user_id=google_user_id
        )
        user = social_account.user
        
        # Log in the existing user
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        
        AuditLog.objects.create(
            actor=user,
            action="auth.google_login",
            entity_type="user",
            entity_id=str(user.id),
            summary=f"User {user.email} signed in with Google",
        )
        
        # Redirect to frontend
        frontend_url = "http://localhost:5173"
        return HttpResponseRedirect(frontend_url)
        
    except SocialAccount.DoesNotExist:
        # Check if a user with this email already exists (password-based account)
        existing_user = User.objects.filter(email__iexact=email).first()
        
        if existing_user:
            # Safe to link: Google has verified email ownership through OAuth
            # Link the Google account to the existing user
            with transaction.atomic():
                # Check if already linked to prevent duplicates
                existing_social = SocialAccount.objects.filter(
                    provider=SocialAccount.Provider.GOOGLE,
                    provider_user_id=google_user_id
                ).first()
                
                if not existing_social:
                    # Create new social account link
                    SocialAccount.objects.create(
                        user=existing_user,
                        provider=SocialAccount.Provider.GOOGLE,
                        provider_user_id=google_user_id,
                        email=email,
                        extra_data={
                            "name": full_name,
                            "given_name": given_name,
                            "family_name": family_name,
                        }
                    )
                    
                    AuditLog.objects.create(
                        actor=existing_user,
                        action="auth.google_linked",
                        entity_type="user",
                        entity_id=str(existing_user.id),
                        summary=f"Linked Google account to existing user {existing_user.email}",
                    )
                
                # Log in the user
                login(request, existing_user, backend="django.contrib.auth.backends.ModelBackend")
                
                AuditLog.objects.create(
                    actor=existing_user,
                    action="auth.google_login",
                    entity_type="user",
                    entity_id=str(existing_user.id),
                    summary=f"User {existing_user.email} signed in with Google (linked account)",
                )
            
            # Redirect to frontend
            frontend_url = "http://localhost:5173"
            return HttpResponseRedirect(frontend_url)
        
        # Create new user and link Google account (NO organization created - user completes setup)
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=given_name[:150],
                last_name=family_name[:150],
            )
            # No password set - this is a Google-only account
            
            # Link Google account
            SocialAccount.objects.create(
                user=user,
                provider=SocialAccount.Provider.GOOGLE,
                provider_user_id=google_user_id,
                email=email,
                extra_data={
                    "name": full_name,
                    "given_name": given_name,
                    "family_name": family_name,
                }
            )
            
            AuditLog.objects.create(
                actor=user,
                action="auth.google_register",
                entity_type="user",
                entity_id=str(user.id),
                summary=f"Registered user {user.email} via Google OAuth (org setup pending)",
            )
            
            # Log in the new user
            # Log in the new user
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        
        # Redirect to frontend
        frontend_url = "http://localhost:5173"
        return HttpResponseRedirect(frontend_url)


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def google_oauth_start(request):
    """
    Step 1: Redirect user to Google's OAuth consent screen.
    Generates a state token for CSRF protection.
    """
    from django.conf import settings
    import secrets
    import urllib.parse
    
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        return Response(
            {
                "error": "Google OAuth is not configured",
                "error_type": "google_oauth_not_configured",
                "detail": "GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET must be set in .env"
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    
    # Generate and store state for CSRF protection
    state = secrets.token_urlsafe(32)
    request.session["google_oauth_state"] = state
    request.session["google_oauth_initiated_at"] = timezone.now().isoformat()
    
    # Build Google OAuth authorization URL
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return Response({"auth_url": auth_url})


@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def google_oauth_callback(request):
    """
    Step 2: Handle Google redirect after user authorization.
    Exchanges the authorization code for tokens, verifies the ID token,
    and creates/authenticates the user.
    """
    from django.conf import settings
    from google.oauth2 import id_token
    from google.auth.transport import requests as google_requests
    import requests
    import urllib.parse
    
    # Check for errors from Google
    error = request.GET.get("error")
    if error:
        frontend_url = "http://localhost:5173"
        error_msg = request.GET.get("error_description", "Google authentication failed")
        return JsonResponse(
            {
                "error": error_msg,
                "error_type": "google_oauth_error",
                "redirect_url": f"{frontend_url}?google_error={urllib.parse.quote(error_msg)}"
            },
            status=400
        )
    
    # Verify state (CSRF protection)
    state_from_google = request.GET.get("state", "")
    state_from_session = request.session.get("google_oauth_state", "")
    
    if not state_from_google or state_from_google != state_from_session:
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "Invalid state parameter",
                "error_type": "google_oauth_csrf_error",
                "redirect_url": f"{frontend_url}?google_error=invalid_state"
            },
            status=400
        )
    
    # Clean up state from session
    request.session.pop("google_oauth_state", None)
    request.session.pop("google_oauth_initiated_at", None)
    
    # Get authorization code
    code = request.GET.get("code")
    if not code:
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "No authorization code received",
                "error_type": "google_oauth_no_code",
                "redirect_url": f"{frontend_url}?google_error=no_code"
            },
            status=400
        )
    
    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    
    try:
        token_response = requests.post(token_url, data=token_data, timeout=10)
        token_response.raise_for_status()
        tokens = token_response.json()
    except Exception as e:
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": f"Failed to exchange code for tokens: {str(e)}",
                "error_type": "google_oauth_token_exchange_error",
                "redirect_url": f"{frontend_url}?google_error=token_exchange_failed"
            },
            status=400
        )
    
    # Verify ID token
    id_token_str = tokens.get("id_token")
    if not id_token_str:
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "No ID token in response",
                "error_type": "google_oauth_no_id_token",
                "redirect_url": f"{frontend_url}?google_error=no_id_token"
            },
            status=400
        )
    
    try:
        # Verify the ID token with Google public keys
        # Use clock_skew_in_seconds to handle minor time differences between servers
        idinfo = id_token.verify_oauth2_token(
            id_token_str,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
            clock_skew_in_seconds=settings.GOOGLE_OAUTH_CLOCK_SKEW_SECONDS
        )
        
        # Verify issuer
        if idinfo["iss"] not in ["accounts.google.com", "https://accounts.google.com"]:
            raise ValueError("Invalid issuer")
        
        # Extract user info
        google_user_id = idinfo["sub"]
        email = idinfo.get("email", "").lower()
        email_verified = idinfo.get("email_verified", False)
        given_name = idinfo.get("given_name", "")
        family_name = idinfo.get("family_name", "")
        full_name = idinfo.get("name", f"{given_name} {family_name}".strip())
        
        if not email or not email_verified:
            raise ValueError("Email not verified or missing")
        
    except ValueError as e:
        import logging
        logger = logging.getLogger(__name__)
        
        # Log the specific verification failure
        error_msg = str(e)
        logger.error(f"Google OAuth ID token verification failed: {error_msg}")
        
        # Detect clock skew issues and log a helpful warning
        if "too early" in error_msg.lower() or "too late" in error_msg.lower():
            logger.warning(
                "Clock skew detected between server and Google; sync system time. "
                f"Current GOOGLE_OAUTH_CLOCK_SKEW_SECONDS: {settings.GOOGLE_OAUTH_CLOCK_SKEW_SECONDS}"
            )
        
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "ID token verification failed",
                "error_type": "google_oauth_verification_error",
                "redirect_url": f"{frontend_url}?google_error=verification_failed"
            },
            status=400
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Google OAuth token verification exception: {str(e)}")
        
        frontend_url = "http://localhost:5173"
        return JsonResponse(
            {
                "error": "ID token verification failed",
                "error_type": "google_oauth_verification_error",
                "redirect_url": f"{frontend_url}?google_error=verification_failed"
            },
            status=400
        )
    
    # Import SocialAccount here to avoid circular import
    from .models import SocialAccount
    
    # Check if this Google account is already linked
    try:
        social_account = SocialAccount.objects.select_related("user").get(
            provider=SocialAccount.Provider.GOOGLE,
            provider_user_id=google_user_id
        )
        user = social_account.user
        
        # Log in the existing user
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        
        AuditLog.objects.create(
            actor=user,
            action="auth.google_login",
            entity_type="user",
            entity_id=str(user.id),
            summary=f"User {user.email} signed in with Google",
        )
        
        # Redirect to frontend
        frontend_url = "http://localhost:5173"
        return HttpResponseRedirect(frontend_url)
        
    except SocialAccount.DoesNotExist:
        # Check if a user with this email already exists (password-based account)
        existing_user = User.objects.filter(email__iexact=email).first()
        
        if existing_user:
            # Safe to link: Google has verified email ownership through OAuth
            # Link the Google account to the existing user
            with transaction.atomic():
                # Check if already linked to prevent duplicates
                existing_social = SocialAccount.objects.filter(
                    provider=SocialAccount.Provider.GOOGLE,
                    provider_user_id=google_user_id
                ).first()
                
                if not existing_social:
                    # Create new social account link
                    SocialAccount.objects.create(
                        user=existing_user,
                        provider=SocialAccount.Provider.GOOGLE,
                        provider_user_id=google_user_id,
                        email=email,
                        extra_data={
                            "name": full_name,
                            "given_name": given_name,
                            "family_name": family_name,
                        }
                    )
                    
                    AuditLog.objects.create(
                        actor=existing_user,
                        action="auth.google_linked",
                        entity_type="user",
                        entity_id=str(existing_user.id),
                        summary=f"Linked Google account to existing user {existing_user.email}",
                    )
                
                # Log in the user
                login(request, existing_user, backend="django.contrib.auth.backends.ModelBackend")
                
                AuditLog.objects.create(
                    actor=existing_user,
                    action="auth.google_login",
                    entity_type="user",
                    entity_id=str(existing_user.id),
                    summary=f"User {existing_user.email} signed in with Google (linked account)",
                )
            
            # Redirect to frontend
            frontend_url = "http://localhost:5173"
            return HttpResponseRedirect(frontend_url)
        
        # Create new user and link Google account
        with transaction.atomic():
            # Create user
            user = User.objects.create_user(
                username=email,
                email=email,
                first_name=given_name[:150],
                last_name=family_name[:150],
            )
            # No password set � this is a Google-only account
            
            # Create default organization
            org_name = f"{full_name}'s Business" if full_name else f"{email.split('@')[0]}'s Business"
            org = Organization.objects.create(name=org_name)
            
            Membership.objects.create(
                organization=org,
                user=user,
                role=Membership.Role.OWNER
            )
            
            # Seed default GST rates
            from products.gst import create_default_gst_rates
            create_default_gst_rates(org)
            
            # Link Google account
            SocialAccount.objects.create(
                user=user,
                provider=SocialAccount.Provider.GOOGLE,
                provider_user_id=google_user_id,
                email=email,
                extra_data={
                    "name": full_name,
                    "given_name": given_name,
                    "family_name": family_name,
                }
            )
            
            AuditLog.objects.create(
                organization=org,
                actor=user,
                action="auth.google_register",
                entity_type="user",
                entity_id=str(user.id),
                summary=f"Registered user {user.email} via Google OAuth with organization {org.name}",
            )
            
            # Log in the new user
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        
        # Redirect to frontend
        frontend_url = "http://localhost:5173"
        return HttpResponseRedirect(frontend_url)
