from django.conf import settings
from django.db import models

from apps_sirae.grados.models import Grados
from apps_sirae.jornadas.models import Jornada


class SedeJornada(models.Model):
    id_sede_jornada = models.AutoField(primary_key=True)
    id_sede = models.ForeignKey(
        'sedes.Sede',
        on_delete=models.CASCADE,
        db_column='id_sede',
        related_name='sede_jornadas',
    )
    id_jornada = models.ForeignKey(
        Jornada,
        on_delete=models.CASCADE,
        db_column='id_jornada',
        related_name='sede_jornadas',
    )
    cupos = models.IntegerField(default=0)

    class Meta:
        db_table = 'sede_jornada'
        unique_together = ('id_sede', 'id_jornada')


class SedeJornadaGrado(models.Model):
    """Distribución de cupos y estado por grado dentro de una jornada de sede."""

    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
    ]

    id_sede_jornada_grado = models.AutoField(primary_key=True)
    id_sede_jornada = models.ForeignKey(
        SedeJornada,
        on_delete=models.CASCADE,
        db_column='id_sede_jornada',
        related_name='grados_atendidos',
    )
    id_grado = models.ForeignKey(
        Grados,
        on_delete=models.PROTECT,
        db_column='id_grado',
        related_name='sede_jornadas_atencion',
    )
    cupos = models.PositiveIntegerField(default=0)
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='ACTIVO',
    )

    class Meta:
        db_table = 'sede_jornada_grado'
        ordering = ['id_grado__id_grado']
        constraints = [
            models.UniqueConstraint(
                fields=('id_sede_jornada', 'id_grado'),
                name='unique_grado_per_sede_jornada',
            ),
        ]

    def __str__(self):
        return f'{self.id_sede_jornada} - {self.id_grado} ({self.estado})'


class HistorialConfiguracionSede(models.Model):
    """Registro de auditoría de cada cambio en la configuración de jornadas/cupos."""

    id_historial = models.AutoField(primary_key=True)
    id_sede = models.ForeignKey(
        'sedes.Sede',
        on_delete=models.CASCADE,
        db_column='id_sede',
        related_name='historial_configuracion',
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_configuracion_sedes',
    )
    fecha_hora = models.DateTimeField(auto_now_add=True)
    valores_anteriores = models.JSONField(default=dict)
    valores_nuevos = models.JSONField(default=dict)

    class Meta:
        db_table = 'historial_configuracion_sede'
        ordering = ('-fecha_hora', '-id_historial')