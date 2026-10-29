from django.urls import path
from . import views

urlpatterns = [
    path("imports/invoice-template/csv/", views.invoice_template_csv),
    path("imports/invoice-template/xlsx/", views.invoice_template_xlsx),
    path("imports/invoices/", views.invoice_upload),
    path("imports/invoices/<uuid:batch_id>/", views.invoice_batch_detail),
    path("imports/invoices/<uuid:batch_id>/commit/", views.invoice_batch_commit),
]
