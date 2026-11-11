from decimal import Decimal
from django.db import models


class UnidadMedida(models.Model):
    MAGNITUDES = [
        ('MASA', 'Masa (g, kg, lb)'),
        ('VOLUMEN', 'Volumen (ml, L)'),
        ('UNIDAD', 'Unidad individual (und, pza)'),
    ]

    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
    ]

    id_unidad_medida = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    abreviatura = models.CharField(max_length=20)
    tipo_magnitud = models.CharField(
        max_length=20,
        choices=MAGNITUDES,
        default='MASA',
        help_text='Magnitud física de la unidad para validar compatibilidad de conversiones.'
    )
    factor_conversion_base = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=Decimal('1.000000'),
        help_text='Factor respecto a la unidad base (Masa=g, Volumen=ml, Unidad=und). Ej: kg=1000, g=1, L=1000, ml=1.'
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='ACTIVO'
    )

    class Meta:
        db_table = 'unidades_medida'

    def __str__(self):
        return f"{self.nombre} ({self.abreviatura})"


class EquivalenciaUnidad(models.Model):
    """
    Equivalencia técnica específica por producto para permitir conversiones
    entre magnitudes distintas (ej. 1 Unidad de Huevo = 55 g, o 1 Litro de Leche = 1030 g).
    """
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
    ]

    id_equivalencia = models.AutoField(primary_key=True)
    id_ingrediente = models.ForeignKey(
        'ingredientes.Ingrediente',
        on_delete=models.CASCADE,
        db_column='id_ingrediente',
        related_name='equivalencias_unidades'
    )
    id_unidad_origen = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
        db_column='id_unidad_origen',
        related_name='equivalencias_origen'
    )
    id_unidad_destino = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
        db_column='id_unidad_destino',
        related_name='equivalencias_destino'
    )
    factor_conversion = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        help_text='Cantidad de unidad destino equivalente a 1 unidad origen para este producto.'
    )
    observaciones = models.TextField(blank=True, default='')
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='ACTIVO'
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'equivalencias_unidades'
        ordering = ['-id_equivalencia']

    def __str__(self):
        return (
            f"{self.id_ingrediente} | 1 {self.id_unidad_origen.abreviatura} = "
            f"{self.factor_conversion} {self.id_unidad_destino.abreviatura}"
        )
