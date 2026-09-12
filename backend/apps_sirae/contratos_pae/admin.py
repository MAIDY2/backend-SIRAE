from django.contrib import admin

from .models import Contrato


@admin.register(Contrato)
class ContratoAdmin(admin.ModelAdmin):
    list_display = (
        'id_contrato',
        'numero_cor',
        'institucion',
        'zona',
        'fecha_inicio',
        'fecha_fin',
        'estado',
    )
   
