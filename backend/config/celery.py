import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("finpilot")
app.config_from_object("django.conf:settings", namespace="CELERY")
# Beat scheduler backed by database (django-celery-beat)
app.conf.beat_scheduler = "django_celery_beat.schedulers:DatabaseScheduler"
# Auto-discover tasks in every installed app
app.autodiscover_tasks()
