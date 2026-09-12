from django.contrib import admin

from .models import Plato


@admin.register(Plato)
class PlatoAdmin(admin.ModelAdmin):
<<<<<<< HEAD
    list_display = ('id_plato', 'nombre_plato', 'id_seccion', 'componente')
    search_fields = ('nombre_plato', 'componente')
=======

    list_display = ('id_plato','nombre_plato','id_seccion','componente',)
    search_fields = ('nombre_plato','componente',)
>>>>>>> f7be33e5f87ff6d750f1ab487464488a2fc533ad
    list_filter = ('id_seccion',)