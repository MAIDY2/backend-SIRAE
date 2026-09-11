from django.db import models

from django.db import models


class Ingrediente(models.Model):
    nombre_ingrediente = models.CharField(max_length=100)
    descripcion = models.TextField()
    imagen_ingrediente = models.CharField(max_length=255)
    marca_ingrediente = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre_ingrediente