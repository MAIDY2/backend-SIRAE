from django.contrib import admin

from .models import CalculoEntrega, Entrega


admin.site.register(Entrega)
admin.site.register(CalculoEntrega)