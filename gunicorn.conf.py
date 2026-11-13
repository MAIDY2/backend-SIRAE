import os
import sys

# Puerto dinámico inyectado por Render (por defecto 10000 en Render)
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Asegurar backend en sys.path si se arranca desde la raíz
backend_dir = os.path.join(os.path.dirname(__file__), "backend")
if os.path.exists(backend_dir) and backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Configuración de workers y concurrencia
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("PYTHON_MAX_THREADS", "2"))
worker_class = "gthread"
timeout = int(os.environ.get("WEB_TIMEOUT", "120"))
keepalive = 5

# Logs dirigidos a la consola para visibilidad en el panel de Render
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")


def on_starting(server):
    """Ejecuta migraciones automáticas al iniciar el servidor gunicorn en Render."""
    import subprocess
    try:
        manage_py = os.path.join(backend_dir, "manage.py") if os.path.exists(backend_dir) else os.path.join(os.path.dirname(__file__), "manage.py")
        if os.path.exists(manage_py):
            print("[gunicorn] Ejecutando migraciones automáticas de base de datos...")
            subprocess.run([sys.executable, manage_py, "migrate", "--noinput"], check=True)
            print("[gunicorn] Migraciones de base de datos aplicadas exitosamente.")
    except Exception as e:
        print(f"[gunicorn] Advertencia al ejecutar migraciones en on_starting: {e}")
