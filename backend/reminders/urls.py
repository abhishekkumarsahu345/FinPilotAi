from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import ReminderTemplateViewSet, ReminderPolicyViewSet, ReminderJobViewSet

router = DefaultRouter()
router.register("reminders/templates", ReminderTemplateViewSet, basename="reminder-templates")
router.register("reminders/policies", ReminderPolicyViewSet, basename="reminder-policies")
router.register("reminders/jobs", ReminderJobViewSet, basename="reminder-jobs")

urlpatterns = [path("", include(router.urls))]
