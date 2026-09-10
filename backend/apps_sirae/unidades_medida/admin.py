from django.contrib import admin
from .models import UnidadMedida


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ('id_unidad_medida', 'nombre', 'abreviatura', 'descripcion')
    search_fields = ('nombre', 'abreviatura')