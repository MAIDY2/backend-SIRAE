from django.contrib import admin
from apps_sirae.roles.models import Rol


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ('id_rol', 'nombre', 'descripcion')
    search_fields = ('nombre',)
    ordering = ('id_rol',)
