from django.db import models
from apps_sirae.grados.models import Grados

class AsistenciaDiaria(models.Model):
    id_asistencia = models.AutoField(primary_key=True)
    
    # 🔗 RELACIÓN CLAVE CON GRADOS
    id_grado = models.ForeignKey(
        Grados, 
        on_delete=models.CASCADE, 
        db_column='id_grado',
        related_name='asistencias' # Te permite hacer grado.asistencias.all()
    )
    
    fecha = models.DateField()
    ninos_presentes = models.PositiveIntegerField()
    
    id_usuario_manipuladora = models.IntegerField(
        db_column='id_usuario_manipuladorajefe',
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'asistencia_diaria'
        managed = True