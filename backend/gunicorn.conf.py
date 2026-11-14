import os

# Puerto dinámico inyectado por Render (por defecto 10000 en Render)
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Configuración de workers y concurrencia optimizada para arranque inmediato
workers = int(os.environ.get("WEB_CONCURRENCY", "2"))
threads = int(os.environ.get("PYTHON_MAX_THREADS", "2"))
worker_class = "gthread"
timeout = int(os.environ.get("WEB_TIMEOUT", "120"))
keepalive = 5

# Logs dirigidos a la consola para visibilidad en el panel de Render
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
