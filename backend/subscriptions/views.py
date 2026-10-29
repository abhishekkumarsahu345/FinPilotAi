from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from core.permissions import HasOrganizationAccess
from .models import Plan, Subscription


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def subscription_status(request):
    org = request.membership.organization
    sub = Subscription.objects.filter(organization=org).order_by("-created_at").first()
    plans = Plan.objects.filter(active=True)
    return Response({
        "subscription": {
            "status": sub.status if sub else "none",
            "plan": sub.plan.name if sub else None,
            "period_end": str(sub.period_end) if sub and sub.period_end else None,
        } if sub else None,
        "available_plans": [
            {
                "id": str(p.id),
                "tier": p.tier,
                "name": p.name,
                "max_users": p.max_users,
                "max_invoices_per_month": p.max_invoices_per_month,
                "max_messages_per_month": p.max_messages_per_month,
                "max_ai_requests_per_month": p.max_ai_requests_per_month,
                "price_monthly_minor": p.price_monthly_minor,
            }
            for p in plans
        ],
    })
