"""
Platform administration endpoints.
Only accessible to Django staff/superuser accounts.
No unrestricted access to tenant financial data by default.
"""
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.contrib.auth import get_user_model

from core.models import Organization, AuditLog

User = get_user_model()


class IsStaffPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_staff or request.user.is_superuser


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsStaffPermission])
def org_list(request):
    orgs = Organization.objects.all().order_by("-created_at")[:100]
    return Response([
        {
            "id": str(o.id),
            "name": o.name,
            "status": o.status,
            "default_currency": o.default_currency,
            "created_at": o.created_at.isoformat(),
        }
        for o in orgs
    ])


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsStaffPermission])
def user_list(request):
    users = User.objects.all().order_by("-date_joined")[:200]
    return Response([
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.get_full_name(),
            "is_active": u.is_active,
            "date_joined": u.date_joined.isoformat(),
        }
        for u in users
    ])


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, IsStaffPermission])
def audit_log_admin(request):
    """Platform-level audit log — all organizations."""
    logs = AuditLog.objects.select_related("actor", "organization")[:200]
    return Response([
        {
            "id": l.id,
            "organization": l.organization.name if l.organization else None,
            "actor": l.actor.email if l.actor else "system",
            "action": l.action,
            "entity_type": l.entity_type,
            "entity_id": l.entity_id,
            "summary": l.summary,
            "created_at": l.created_at.isoformat(),
        }
        for l in logs
    ])
