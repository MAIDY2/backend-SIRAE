from django.db import models

class Grados(models.Model):
    id_grado = models.AutoField(primary_key=True)
    nombre_grado = models.CharField(max_length=100)

    def __str__(self):
        return self.nombre_grado

    class Meta:
        db_table = 'grados'
        managed = False