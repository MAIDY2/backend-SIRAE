from django.contrib import admin

from .models import Jornada


@admin.register(Jornada)
class JornadaAdmin(admin.ModelAdmin):
    list_display = (
        'id_jornada',
        'nombre_jornada',
    )
