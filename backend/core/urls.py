from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    OrganizationViewSet, CustomerViewSet, InvoiceViewSet, PaymentViewSet,
    dashboard, aging, audit_logs, members_list, me, csrf, sign_in, sign_out, register,
)

router = DefaultRouter()
router.register("organizations", OrganizationViewSet, basename="organizations")
router.register("customers", CustomerViewSet, basename="customers")
router.register("invoices", InvoiceViewSet, basename="invoices")
router.register("payments", PaymentViewSet, basename="payments")

urlpatterns = [
    # Auth
    path("auth/csrf/", csrf),
    path("auth/register/", register),
    path("auth/login/", sign_in),
    path("auth/logout/", sign_out),
    path("auth/me/", me),
    # Dashboard and reports
    path("dashboard/", dashboard),
    path("reports/aging/", aging),
    path("audit-logs/", audit_logs),
    path("members/", members_list),
    # Router-registered viewsets
    path("", include(router.urls)),
]
