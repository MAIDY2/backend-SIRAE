from django.db import models


class pasospreparacion(models.Model):
    id = models.AutoField(primary_key=True)
    id_plato = models.IntegerField()
    numero_paso = models.CharField(max_length=100)
    descripcion = models.TextField()

    def __str__(self):
        return f"pasospreparacion {self.numero_paso} - {self.descripcion}"