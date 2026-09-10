from django.db import models
from django.utils import timezone


class Notificacion(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    id_usuario = models.IntegerField()
    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    fecha_hora = models.DateTimeField(default=timezone.now)
    leida = models.BooleanField(default=False)

    class Meta:
        db_table = 'notificaciones'