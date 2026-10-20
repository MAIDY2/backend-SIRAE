from django.db import models

class Ingrediente(models.Model):
    nombre = models.CharField(max_length=100)
    unidad_medida = models.CharField(max_length=50) # Ej: Kilogramos, Litros, Unidades
    
    # upload_to indica la subcarpeta dentro de media/
    imagen = models.ImageField(upload_to='ingredientes/', null=True, blank=True)

    def __str__(self):
        return self.nombre