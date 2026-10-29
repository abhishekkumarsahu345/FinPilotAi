from django.urls import path
from .views import export_invoices, export_customers, export_payments

urlpatterns = [
    path("exports/invoices/", export_invoices),
    path("exports/customers/", export_customers),
    path("exports/payments/", export_payments),
]
