from django.apps import AppConfig


class InventarioConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps_sirae.inventario'

    def ready(self):
        import apps_sirae.inventario.signals