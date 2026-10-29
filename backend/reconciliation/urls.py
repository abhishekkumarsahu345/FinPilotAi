from django.urls import path
from . import views

urlpatterns = [
    path("imports/bank-statements/", views.bank_statement_upload),
    path("imports/bank-statements/<uuid:batch_id>/confirm-mapping/", views.bank_statement_confirm_mapping),
    path("reconciliation/", views.reconciliation_list),
    path("reconciliation/<uuid:match_id>/confirm/", views.confirm_match),
    path("reconciliation/<uuid:match_id>/reject/", views.reject_match),
]
