
from django.db import models
from django.utils import timezone


class Notificacion(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    id_usuario = models.IntegerField()
    id_remitente = models.IntegerField(null=True, blank=True)
    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    imagen_url = models.URLField(max_length=1000, blank=True, null=True)
    fecha_hora = models.DateTimeField(default=timezone.now)
    leida = models.BooleanField(default=False)

    class Meta:
        db_table = 'notificaciones'
