from django.contrib import admin

from .models import CategoriaInventario


@admin.register(CategoriaInventario)
class CategoriaInventarioAdmin(admin.ModelAdmin):
    list_display = (
        'id_categoria_inventario',
        'nombre_categoria',
    )
