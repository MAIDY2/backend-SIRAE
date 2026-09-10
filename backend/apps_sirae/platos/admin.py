from django.contrib import admin
from .models import Plato


@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display = ('id_plato', 'nombre', 'id_seccion_menu', 'precio', 'activo')
    search_fields = ('nombre',)
    list_filter = ('id_seccion_menu', 'activo')