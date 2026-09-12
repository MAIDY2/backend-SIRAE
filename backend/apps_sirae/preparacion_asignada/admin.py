from django.contrib import admin

from .models import PreparacionAsignada


@admin.register(PreparacionAsignada)
class PreparacionAsignadaAdmin(admin.ModelAdmin):
    list_display = (
        'id_preparacion_asignada',
        'id_menu',
        'id_plato',
        'id_usuario_manipuladora',
        'id_turno',
        'fecha',
        'hora_programada',
        'estado_preparacion',
    )
    
