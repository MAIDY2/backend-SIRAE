from django.conf import settings
from django.db import models


class Institucion(models.Model):
    id_institucion = models.AutoField(primary_key=True)
    nombre_institucion = models.CharField(max_length=150)
    nit = models.CharField(max_length=50, unique=True)
    representante_legal = models.CharField(max_length=150, blank=True, null=True)
    telefono = models.CharField(max_length=30, blank=True, null=True)
    correo_contacto = models.CharField(max_length=150, blank=True, null=True)
    estado = models.CharField(max_length=20, default='ACTIVO')

    class Meta:
        db_table = 'instituciones'

    def __str__(self):
        return f"{self.nombre_institucion} ({self.nit})"


class SupervisorInstitucion(models.Model):
    id_supervisor_institucion = models.AutoField(primary_key=True)
    id_supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        db_column='id_supervisor',
        related_name='instituciones_asignadas'
    )
    id_institucion = models.ForeignKey(
        Institucion,
        on_delete=models.CASCADE,
        db_column='id_institucion',
        related_name='supervisores_asignados'
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'supervisor_instituciones'
        unique_together = ('id_supervisor', 'id_institucion')

    def __str__(self):
        return f"Supervisor {self.id_supervisor_id} -> Institución {self.id_institucion_id}"
    