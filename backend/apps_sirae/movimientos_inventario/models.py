from django.db import models
from django.conf import settings
# Rutas ajustadas al paquete apps_sirae
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.unidades_medida.models import UnidadMedida

class MovimientoInventario(models.Model):
    id_movimiento_inventario = models.AutoField(primary_key=True)
    id_ingrediente = models.ForeignKey(Ingrediente, on_delete=models.CASCADE, db_column='id_ingrediente')
    id_usuario_manipuladora = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        db_column='id_usuario_manipuladora'
    )
    tipo_movimiento = models.CharField(max_length=50)
    fecha = models.DateTimeField(auto_now_add=True)
    cantidad = models.PositiveIntegerField()
    observaciones = models.TextField(blank=True, null=True)
    id_unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, db_column='id_unidad_medida')

    class Meta:
        db_table = 'movimientos_inventario'

    def __str__(self):
        return f"{self.tipo_movimiento} - {self.id_ingrediente} ({self.cantidad})"