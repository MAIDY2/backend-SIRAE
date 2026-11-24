from django.apps import AppConfig


class NotificacionesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps_sirae.notificaciones'

    def ready(self):
        try:
            import apps_sirae.notificaciones.signals  # noqa: F401
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"No se pudieron registrar las señales n8n: {e}")