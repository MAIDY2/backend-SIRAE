# Despliegue del backend SIRAE en Render

El `render.yaml` espera que `DATABASE_URL` se configure como variable secreta del
servicio. Usa la URL de Neon después de restablecer la contraseña que se compartió
anteriormente; no la guardes en Git ni la pegues en el chat. Mantén `DEBUG=False`
y configura `SECRET_KEY` con un valor privado generado por Render.

Al desplegar, Render instala dependencias, ejecuta las migraciones y recopila los
archivos estáticos. La aplicación se niega a iniciar en producción si no recibe
`DATABASE_URL` o `SECRET_KEY`, para evitar usar SQLite efímera o una clave de
desarrollo por accidente.

Después del primer despliegue, desde **Shell** del servicio ejecuta:

```text
python manage.py seed_roles
python manage.py crear_usuario_prueba
```

El segundo comando pide una contraseña nueva dos veces por cada cuenta creada y
no muestra lo que se escribe. Para restablecer también las cuentas existentes,
añade `--reset-existing-passwords`. Usa contraseñas nuevas y robustas; el comando
no almacena contraseñas en el repositorio.
