"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os
import sys

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

# Ejecutar migraciones automáticas al iniciar en producción (Render / PostgreSQL)
if os.getenv('DATABASE_URL'):
    try:
        from django.core.management import call_command
        call_command('migrate', interactive=False)
    except Exception as _ex:
        import logging
        logging.getLogger('config.wsgi').warning("Auto-migrate en WSGI aviso: %s", _ex)
