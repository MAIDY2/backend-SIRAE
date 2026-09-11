from django.contrib import admin

from .models import Menu


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = (
        'id_menu',
        'id_jornada',
        'fecha',
        'ninos_presentes',
        'estado',
        'id_contrato',
    )
