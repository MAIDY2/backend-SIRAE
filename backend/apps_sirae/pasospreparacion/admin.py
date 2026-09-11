from django.contrib import admin

from .models import pasospreparacion


@admin.register(pasospreparacion)
class pasospreparacion(admin.ModelAdmin):
    list_display = (
        'id_plato',
        'numero_paso',
        'descripcion',
    )
       

    

   


