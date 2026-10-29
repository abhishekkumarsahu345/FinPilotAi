from rest_framework.permissions import BasePermission
from .models import Membership

# Roles that can write financial records
WRITE_ROLES = {Membership.Role.OWNER, Membership.Role.MANAGER, Membership.Role.ACCOUNTANT}
# Roles that can approve reminders / change policies
FINANCE_ROLES = {Membership.Role.OWNER, Membership.Role.MANAGER}
# All roles (any authenticated member)
ALL_ROLES = {r.value for r in Membership.Role}


class HasOrganizationAccess(BasePermission):
    """
    Resolves the active organization from the X-Organization-ID header,
    verifies an active membership, and attaches it to request.membership.
    Read-only methods (GET/HEAD/OPTIONS) pass for any role.
    Mutating methods require WRITE_ROLES.
    """
    def has_permission(self, request, view):
        org_id = (
            request.headers.get("X-Organization-ID")
            or request.query_params.get("organization")
        )
        if not org_id:
            return False
        membership = Membership.objects.select_related("organization").filter(
            user=request.user,
            organization_id=org_id,
            active=True,
        ).first()
        if not membership:
            return False
        request.membership = membership
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return membership.role in WRITE_ROLES


class IsFinanceRole(BasePermission):
    """Requires owner or finance manager role for the active membership."""
    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        if not membership:
            return False
        return membership.role in FINANCE_ROLES


class IsOwner(BasePermission):
    """Requires business owner role."""
    def has_permission(self, request, view):
        membership = getattr(request, "membership", None)
        return membership and membership.role == Membership.Role.OWNER


def require_roles(*roles):
    """Factory: returns a permission class requiring one of the given roles."""
    role_set = set(roles)

    class RolePermission(BasePermission):
        def has_permission(self, request, view):
            membership = getattr(request, "membership", None)
            return bool(membership and membership.role in role_set)

    return RolePermission
