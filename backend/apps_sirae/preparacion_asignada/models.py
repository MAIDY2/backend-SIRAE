from django.db import models

class PreparacionAsignada(models.Model):
    id_preparacion_asignada = models.AutoField(primary_key=True)
    id_menu = models.IntegerField()
    id_plato = models.IntegerField()
    id_usuario_manipuladora = models.IntegerField()
    id_turno = models.IntegerField()
    fecha = models.DateField()
    hora_programada = models.TimeField()
    estado_preparacion = models.CharField(max_length=50, default='Pendiente')
    observaciones = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'preparacion_asignada'

    def __str__(self):
        return f"Preparación {self.id_preparacion_asignada} - Menú {self.id_menu} - Plato {self.id_plato}"