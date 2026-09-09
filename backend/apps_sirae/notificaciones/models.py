from django.db import models


class Notificacion(models.Model):
    id_notificacion = models.AutoField(primary_key=True)
    id_usuario = models.IntegerField()
    titulo = models.CharField(max_length=150)
    mensaje = models.TextField()
    fecha_hora = models.DateTimeField()
    leida = models.BooleanField(default=False)

    class Meta:
        db_table = 'notificaciones'