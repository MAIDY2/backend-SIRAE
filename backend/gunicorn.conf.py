import os

# Puerto dinámico inyectado por Render (por defecto 10000 en Render)
port = os.environ.get("PORT", "10000")
bind = f"0.0.0.0:{port}"

# Configuración de workers: sync es el modo más robusto y rápido para Django en Render
concurrency_env = os.environ.get("WEB_CONCURRENCY")
workers = int(concurrency_env) if concurrency_env and concurrency_env.isdigit() else 1
worker_class = "sync"
timeout = 120
keepalive = 5

# Logs dirigidos inmediatamente a stdout/stderr sin buffer para visibilidad total en Render
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("LOG_LEVEL", "info")
capture_output = True
enable_stdio_inheritance = True
