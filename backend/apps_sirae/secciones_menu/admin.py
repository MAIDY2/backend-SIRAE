from django.contrib import admin
from .models import SeccionMenu


@admin.register(SeccionMenu)
class SeccionMenuAdmin(admin.ModelAdmin):
    list_display = ('id_seccion', 'nombre_seccion', 'id_jornada')
    search_fields = ('nombre_seccion',)
    list_filter = ('id_jornada',)