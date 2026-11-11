from django.db import models
from django.utils import timezone
from apps_sirae.usuarios.models import Usuario


class Mensaje(models.Model):
    id_mensaje = models.AutoField(primary_key=True)
    remitente = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='mensajes_enviados',
        db_column='id_remitente'
    )
    destinatario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='mensajes_recibidos',
        db_column='id_destinatario'
    )
    contenido_texto = models.TextField(blank=True, null=True, default='')
    imagen_url = models.URLField(max_length=1000, blank=True, null=True)
    fecha_envio = models.DateTimeField(default=timezone.now, db_index=True)
    leido = models.BooleanField(default=False, db_index=True)

    class Meta:
        db_table = 'mensajes'
        ordering = ['fecha_envio', 'id_mensaje']

    def __str__(self):
        return f"Mensaje {self.id_mensaje}: {self.remitente_id} -> {self.destinatario_id} ({'leído' if self.leido else 'no leído'})"
