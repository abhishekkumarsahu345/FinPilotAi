from django.urls import include, path
from rest_framework.routers import DefaultRouter
from .views import ReminderTemplateViewSet, ReminderPolicyViewSet, ReminderJobViewSet
from .schedule_views import ReminderScheduleViewSet, ReminderStepViewSet, EnhancedReminderJobViewSet
from .seed_api import seed_default_reminder_setup

router = DefaultRouter()
router.register("reminders/templates", ReminderTemplateViewSet, basename="reminder-templates")
router.register("reminders/policies", ReminderPolicyViewSet, basename="reminder-policies")
router.register("reminders/jobs", ReminderJobViewSet, basename="reminder-jobs")

# New schedule/step system
router.register("reminders/schedules", ReminderScheduleViewSet, basename="reminder-schedules")
router.register("reminders/steps", ReminderStepViewSet, basename="reminder-steps")
router.register("reminders/jobs-v2", EnhancedReminderJobViewSet, basename="reminder-jobs-v2")

urlpatterns = [
    path("", include(router.urls)),
    path("reminders/seed-defaults/", seed_default_reminder_setup, name="seed-defaults"),
]
