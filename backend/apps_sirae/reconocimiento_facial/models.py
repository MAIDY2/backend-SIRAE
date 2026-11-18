from django.conf import settings
from django.db import models


class UsuarioBiometria(models.Model):
    id_biometria = models.AutoField(primary_key=True)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="biometria"
    )
    # Vector facial serializado con pickle (igual a tu instructora)
    embedding = models.BinaryField()
    activo = models.BooleanField(default=True)  # type: ignore
    fecha_registro = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    objects = models.Manager()

    class Meta:
        db_table = "usuarios_biometria"
        verbose_name = "Usuario con registro biométrico"
        verbose_name_plural = "Usuarios con registros biométricos"

    def __str__(self):
        usuario_obj = getattr(self, 'usuario', None)
        correo = getattr(usuario_obj, 'correo', '') if usuario_obj else ''
        return f"Biometría de {correo}"