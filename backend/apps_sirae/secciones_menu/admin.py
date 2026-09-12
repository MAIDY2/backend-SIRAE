from django.contrib import admin

from .models import SeccionMenu


@admin.register(SeccionMenu)
class SeccionMenuAdmin(admin.ModelAdmin):
<<<<<<< HEAD
    list_display = ('id_seccion', 'nombre_seccion', 'id_jornada')
    search_fields = ('nombre_seccion',)
=======

    list_display = ('id_seccion','nombre_seccion','id_jornada',)

    search_fields = ('nombre_seccion', )

>>>>>>> f7be33e5f87ff6d750f1ab487464488a2fc533ad
    list_filter = ('id_jornada',)