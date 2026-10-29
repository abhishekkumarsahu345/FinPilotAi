from datetime import timedelta

from django.contrib.auth import authenticate, get_user_model, login, logout, password_validation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
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
        serializer.validated_data.pop("_warnings", None)
        customer = serializer.save()
        AuditLog.objects.create(
            organization=customer.organization,
            actor=self.request.user,
            action="customer.updated",
            entity_type="customer",
            entity_id=str(customer.id),
            summary=f"Updated customer {customer.name}",
        )

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
    payload = request.data
    email = str(payload.get("email", "")).strip().lower()
    full_name = str(payload.get("full_name", "")).strip()
    org_name = str(payload.get("organization_name", "")).strip()
    password = str(payload.get("password", ""))

    if not email or not full_name or not org_name or not password:
        return Response(
            {"detail": "Name, email, password, and business name are required."},
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

    with transaction.atomic():
        user.set_password(password)
        user.save()
        org = Organization.objects.create(name=org_name)
        Membership.objects.create(
            organization=org, user=user, role=Membership.Role.OWNER
        )
        AuditLog.objects.create(
            organization=org,
            actor=user,
            action="auth.register",
            entity_type="user",
            entity_id=str(user.id),
            summary=f"Registered user {user.email} with organization {org.name}",
        )
        login(request, user)

    return Response(
        {"detail": "Account created", "organization_id": str(org.id)},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
def sign_out(request):
    if request.user.is_authenticated:
        AuditLog.objects.create(
            actor=request.user,
            action="auth.logout",
            entity_type="user",
            entity_id=str(request.user.id),
            summary=f"User {request.user.email} signed out",
        )
    logout(request)
    return Response({"detail": "Signed out"})
