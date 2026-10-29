from django.urls import path
from .views import forecast_view

urlpatterns = [
    path("forecasts/", forecast_view),
]
