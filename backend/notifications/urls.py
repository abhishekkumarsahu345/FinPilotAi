from django.urls import path
from .views import notifications_list, mark_read, mark_all_read

urlpatterns = [
    path("notifications/", notifications_list),
    path("notifications/mark-all-read/", mark_all_read),
    path("notifications/<uuid:notification_id>/read/", mark_read),
]
