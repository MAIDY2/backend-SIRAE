from django.contrib import admin
from .models import SeccionMenu


@admin.register(SeccionMenu)
class SeccionMenuAdmin(admin.ModelAdmin):
    list_display = ('id_seccion_menu', 'nombre', 'activo')
    search_fields = ('nombre',)
    list_filter = ('activo',)