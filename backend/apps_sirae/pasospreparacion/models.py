from django.db import models


class pasospreparacion(models.Model):
    id_plato= models.AutoField(primary_key=True)
    numero_paso = models.CharField(max_length=100)
    descripcion = models.CharField(max_length=100)
    
    def __str__(self):
        return f"pasospreparacion {self.numero_paso} - {self.descripcion}"