from django.contrib import admin
from .models import DetallePlato


@admin.register(DetallePlato)
class DetallePlatoAdmin(admin.ModelAdmin):
    list_display = ('id_detalle_plato', 'id_plato', 'ingrediente', 'cantidad', 'id_unidad_medida')
    search_fields = ('ingrediente', 'id_plato__nombre')
    list_filter = ('id_unidad_medida',)