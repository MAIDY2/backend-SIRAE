from django.contrib import admin
from .models import UnidadMedida


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('id_unidad_medida', 'nombre_unidad', 'abreviatura')
    search_fields = ('nombre_unidad', 'abreviatura')