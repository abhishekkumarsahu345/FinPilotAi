from django.urls import path
from .views import org_list, user_list, audit_log_admin

urlpatterns = [
    path("admin/orgs/", org_list),
    path("admin/users/", user_list),
    path("admin/audit-logs/", audit_log_admin),
]
