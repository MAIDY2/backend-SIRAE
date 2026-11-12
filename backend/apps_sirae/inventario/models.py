from decimal import Decimal
from django.conf import settings
from django.db import models


class Inventario(models.Model):
    objects = models.Manager()

    id_inventario = models.AutoField(primary_key=True)
    id_ingrediente = models.IntegerField()
    cantidad_actual = models.DecimalField(max_digits=10, decimal_places=2)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=2)
    id_unidad_medida = models.IntegerField()
    id_institucion = models.ForeignKey(
        'instituciones.Institucion',
        on_delete=models.CASCADE,
        db_column='id_institucion',
        null=True,
        blank=True,
        related_name='inventarios'
    )
    id_sede = models.ForeignKey(
        'sedes.Sede',
        on_delete=models.CASCADE,
        db_column='id_sede',
        null=True,
        blank=True,
        related_name='inventarios'
    )

    class Meta:
        db_table = 'inventario'

    def __str__(self):
        return f"Inventario {self.id_inventario} - Ingrediente {self.id_ingrediente}"


class AsignacionInventario(models.Model):
    """Cupo o reserva de inventario asignado por SuperAdmin a una institución desde Bodega Central."""

    ESTADOS = [
        ('ACTIVA', 'Activa'),
        ('COMPLETADA', 'Completada'),
        ('ANULADA', 'Anulada'),
    ]

    id_asignacion = models.AutoField(primary_key=True)
    codigo_lote = models.CharField(max_length=64, blank=True, default='', db_index=True)
    id_institucion = models.ForeignKey(
        'instituciones.Institucion',
        on_delete=models.CASCADE,
        db_column='id_institucion',
        related_name='asignaciones_inventario',
    )
    id_contrato = models.ForeignKey(
        'contratos_pae.Contrato',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_contrato',
        related_name='asignaciones_inventario',
    )
    id_ingrediente = models.ForeignKey(
        'ingredientes.Ingrediente',
        on_delete=models.RESTRICT,
        db_column='id_ingrediente',
        related_name='asignaciones_inventario',
    )
    id_unidad_medida = models.ForeignKey(
        'unidades_medida.UnidadMedida',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_unidad_medida',
        related_name='asignaciones_inventario',
    )
    cantidad_asignada = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    cantidad_despachada = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    periodo_inicio = models.DateField(null=True, blank=True)
    periodo_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='ACTIVA')
    observaciones = models.TextField(blank=True, default='')
    id_usuario_asignador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_usuario_asignador',
        related_name='asignaciones_realizadas',
    )
    fecha_asignacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'asignaciones_inventario'
        ordering = ['-fecha_asignacion', '-id_asignacion']

    @property
    def cantidad_pendiente(self) -> Decimal:
        asignada = Decimal(str(self.cantidad_asignada or '0.000'))
        despachada = Decimal(str(self.cantidad_despachada or '0.000'))
        return max(Decimal('0.000'), asignada - despachada)

    def __str__(self):
        return (
            f"Asignación {self.id_asignacion} - Inst {self.id_institucion_id} "
            f"- Ing {self.id_ingrediente_id} ({self.estado})"
        )
