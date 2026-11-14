"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# Ejecutar migraciones automáticas en segundo plano en producción (Render / PostgreSQL)
# Se ejecuta en un hilo independiente (daemon) para no retrasar el inicio de Gunicorn ni activar el timeout de Render
if os.getenv('DATABASE_URL'):
    import threading
    def _auto_migrate():
        try:
            from apps_sirae.usuarios.api.views import asegurar_columnas_criticas
            asegurar_columnas_criticas()
        except Exception:
            pass
        try:
            from django.core.management import call_command
            call_command('migrate', interactive=False)
            print("[SIRAE WSGI] Migraciones automáticas aplicadas exitosamente.")
        except Exception as _ex:
            import logging
            logging.getLogger('config.wsgi').warning("Auto-migrate en WSGI aviso: %s", _ex)

    threading.Thread(target=_auto_migrate, daemon=True, name="sirae-auto-migrate").start()
