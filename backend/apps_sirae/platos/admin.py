from django.contrib import admin
from .models import Plato


@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
    list_display = ('id_plato', 'nombre_plato', 'id_seccion', 'componente')
    search_fields = ('nombre_plato', 'componente')
    list_filter = ('id_seccion',)