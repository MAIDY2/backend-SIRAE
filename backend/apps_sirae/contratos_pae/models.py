from django.db import models


class Contrato(models.Model):
    PERIODICIDAD_CHOICES = [
        ('DIARIA', 'Diaria'),
        ('SEMANAL', 'Semanal'),
        ('QUINCENAL', 'Quincenal'),
        ('MENSUAL', 'Mensual'),
        ('PERSONALIZADA', 'Personalizada'),
    ]

    DIAS_POR_PERIODICIDAD = {
        'DIARIA': 1,
        'SEMANAL': 5,
        'QUINCENAL': 10,
        'MENSUAL': 20,
    }

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
    periodicidad_perecederos = models.CharField(
        max_length=20,
        choices=PERIODICIDAD_CHOICES,
        default='SEMANAL',
        help_text="Periodicidad de abastecimiento para productos perecederos"
    )
    dias_cobertura_perecederos = models.PositiveIntegerField(
        default=5,
        help_text="Días de cobertura por entrega para productos perecederos"
    )
    periodicidad_no_perecederos = models.CharField(
        max_length=20,
        choices=PERIODICIDAD_CHOICES,
        default='MENSUAL',
        help_text="Periodicidad de abastecimiento para productos no perecederos"
    )
    dias_cobertura_no_perecederos = models.PositiveIntegerField(
        default=20,
        help_text="Días de cobertura por entrega para productos no perecederos"
    )

    def obtener_dias_cobertura(self, es_perecedero: bool) -> int:
        """Retorna los días de cobertura configurados según si el producto es perecedero o no."""
        if es_perecedero:
            if self.dias_cobertura_perecederos and self.dias_cobertura_perecederos > 0:
                return int(self.dias_cobertura_perecederos)
            return self.DIAS_POR_PERIODICIDAD.get((self.periodicidad_perecederos or '').upper(), 5)
        if self.dias_cobertura_no_perecederos and self.dias_cobertura_no_perecederos > 0:
            return int(self.dias_cobertura_no_perecederos)
        return self.DIAS_POR_PERIODICIDAD.get((self.periodicidad_no_perecederos or '').upper(), 20)

    class Meta:
        db_table = 'contrato_pae'
        managed = True

    def __str__(self):
        nom = self.institucion or (self.id_institucion.nombre_institucion if self.id_institucion else 'Sin institucion')
        return f"Contrato {self.numero_cor} - {nom} ({self.estado})"