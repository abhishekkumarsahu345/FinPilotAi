from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from core.permissions import HasOrganizationAccess
from .models import Notification, NotificationPreference


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def notifications_list(request):
    """List notifications for the current user in the active organization."""
    # Get base queryset (without slicing yet)
    base_qs = Notification.objects.filter(
        recipient=request.user,
        organization=request.membership.organization,
    )
    
    # Calculate unread count from base queryset (before slicing)
    unread_count = base_qs.filter(read_at__isnull=True).count()
    
    # Now get the limited list of notifications
    notifications = base_qs.order_by("-created_at")[:50]
    
    return Response({
        "unread_count": unread_count,
        "notifications": [
            {
                "id": str(n.id),
                "event_type": n.event_type,
                "entity_type": n.entity_type,
                "entity_id": n.entity_id,
                "payload": n.payload,
                "read": n.read_at is not None,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
    })


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def mark_read(request, notification_id):
    """Mark a single notification as read."""
    try:
        notif = Notification.objects.get(
            id=notification_id,
            recipient=request.user,
            organization=request.membership.organization,
        )
    except Notification.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if notif.read_at is None:
        notif.read_at = timezone.now()
        notif.save()
    return Response({"detail": "Marked as read."})


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated, HasOrganizationAccess])
def mark_all_read(request):
    """Mark all unread notifications as read for the current user."""
    Notification.objects.filter(
        recipient=request.user,
        organization=request.membership.organization,
        read_at__isnull=True,
    ).update(read_at=timezone.now())
    return Response({"detail": "All notifications marked as read."})
