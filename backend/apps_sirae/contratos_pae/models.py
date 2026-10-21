from django.db import models


class Contrato(models.Model):
    id_contrato = models.AutoField(primary_key=True)
    numero_cor = models.CharField(max_length=100, null=True, blank=True)
    institucion = models.CharField(max_length=150, null=True, blank=True)
    zona = models.CharField(max_length=100, null=True, blank=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=50, null=True, blank=True)

    id_institucion = models.ForeignKey(
        'instituciones.Institucion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_institucion',
        related_name='contratos'
    )
    id_sede = models.ForeignKey(
        'sedes.Sede',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_sede',
        related_name='contratos'
    )
    id_usuario_supervisor = models.ForeignKey(
        'usuarios.Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_usuario_supervisor',
        related_name='contratos_supervisados'
    )
    id_jornada = models.ForeignKey(
        'jornadas.Jornada',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_jornada',
        related_name='contratos'
    )
    cupos = models.PositiveIntegerField(
        default=0,
        help_text="Cantidad de cupos asignados a la institución/sede"
    )

    class Meta:
        db_table = 'contrato_pae'
        managed = True

    def __str__(self):
        nom = self.institucion or (self.id_institucion.nombre_institucion if self.id_institucion else 'Sin institucion')
        return f"Contrato {self.numero_cor} - {nom} ({self.estado})"