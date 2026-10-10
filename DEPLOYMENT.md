# Despliegue del backend SIRAE en Render

El `render.yaml` espera que `DATABASE_URL` se configure como variable secreta del
servicio. Usa la URL de Neon después de restablecer la contraseña que se compartió
anteriormente; no la guardes en Git ni la pegues en el chat. Mantén `DEBUG=False`
y configura `SECRET_KEY` con un valor privado generado por Render.

Al desplegar, Render instala dependencias, ejecuta las migraciones y recopila los
archivos estáticos. La aplicación se niega a iniciar en producción si no recibe
`DATABASE_URL` o `SECRET_KEY`, para evitar usar SQLite efímera o una clave de
desarrollo por accidente.

La recuperación de contraseña envía un código de seis dígitos válido durante
10 minutos. Para que los correos salgan en producción, configura en Render las
variables `EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend`,
`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS`, `EMAIL_HOST_USER`,
`EMAIL_HOST_PASSWORD` y `DEFAULT_FROM_EMAIL`. Mantén las credenciales de correo
como variables secretas. En producción, la recuperación devuelve un error si
faltan las credenciales SMTP; no informa que el mensaje fue enviado si el backend
solo puede escribirlo en los logs del servidor.

Solo para pruebas con cuentas sin buzón, se puede habilitar `PASSWORD_RESET_EXPOSE_CODE=True`
y establecer `PASSWORD_RESET_EXPOSE_CODE_EMAILS` con una lista separada por comas de
correos de prueba. Para esas cuentas el código de un solo uso se devuelve al frontend
en `debug_code` en vez de enviarse por SMTP. Esto permite a cualquier persona que
conozca el correo solicitar y ver el código; no habilites esta opción para cuentas
reales ni en una aplicación pública. Déjala desactivada y elimina la lista al terminar
las pruebas.

El frontend solicita el código con `POST /api/auth/recuperar-password/` y el
campo `correo`. Después envía `correo`, `codigo`, `nueva_password` y
`confirmar_password` a `POST /api/auth/confirmar-recuperacion-password/`.
El código se invalida tras cinco intentos fallidos y solo se puede usar una vez.

Después del primer despliegue, desde **Shell** del servicio ejecuta:

```text
python manage.py seed_roles
python manage.py crear_usuario_prueba
```

El segundo comando pide una contraseña nueva dos veces por cada cuenta creada y
no muestra lo que se escribe. Para restablecer también las cuentas existentes,
añade `--reset-existing-passwords`. Usa contraseñas nuevas y robustas; el comando
no almacena contraseñas en el repositorio.

Si necesitas sembrar las cuentas en un despliegue sin Shell, configura
temporalmente en Render las variables secretas `SIRAE_ADMIN_PASSWORD`,
`SIRAE_SUPERVISOR_PASSWORD`, `SIRAE_JEFE_PASSWORD` y
`SIRAE_MANIPULADORA_PASSWORD`, y ejecuta el comando con `--non-interactive`.
Retira esas variables después de verificar que las cuentas se crearon.
