from django.contrib import admin
from .models import DetallePlato


@admin.register(DetallePlato)
class DetallePlatoAdmin(admin.ModelAdmin):
    list_display = ('id_detalle_plato', 'id_menu', 'id_plato', 'porcion_por_nino', 'total_a_preparar', 'unidad_total', 'estado_preparacion')
<<<<<<< HEAD
    search_fields = ('id_plato__nombre_plato', 'unidad_total', 'estado_preparacion')
    list_filter = ('estado_preparacion', 'id_menu')
=======
    search_fields = ('unidad_total', 'estado_preparacion')
>>>>>>> f7be33e5f87ff6d750f1ab487464488a2fc533ad
