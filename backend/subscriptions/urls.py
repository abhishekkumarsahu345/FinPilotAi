from django.urls import path
from .views import subscription_status

urlpatterns = [
    path("subscriptions/", subscription_status),
]
