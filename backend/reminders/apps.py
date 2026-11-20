from django.apps import AppConfig


class RemindersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "reminders"
    verbose_name = "Reminders"
    
    def ready(self):
        # Import and register signal handlers
        import reminders.signals
