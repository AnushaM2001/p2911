# user_panel/apps.py
from django.apps import AppConfig

class UserPanelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'user_panel'

    def ready(self):
        # ensure signals are registered
        import user_panel.signals  # noqa: F401
