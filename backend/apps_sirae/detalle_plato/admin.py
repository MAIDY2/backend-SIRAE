from django.contrib import admin
from .models import DetallePlato


@admin.register(DetallePlato)
class DetallePlatoAdmin(admin.ModelAdmin):
    list_display = ('id_detalle_plato', 'id_menu', 'id_plato', 'porcion_por_nino', 'total_a_preparar', 'unidad_total', 'estado_preparacion')
    search_fields = ('unidad_total', 'estado_preparacion')