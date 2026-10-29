from django.urls import path
from .views import ask_assistant

urlpatterns = [
    path("assistant/", ask_assistant),
]
