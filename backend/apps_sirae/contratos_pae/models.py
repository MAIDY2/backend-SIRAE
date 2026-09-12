from django.db import models


class Contrato(models.Model):
    id_contrato = models.AutoField(primary_key=True)
    numero_cor = models.CharField(max_length=100)
    institucion = models.CharField(max_length=100)
    zona = models.CharField(max_length=100)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=50, default='Activo')
    
    def __str__(self):
        return f"Contrato {self.numero_cor} - {self.institucion} ({self.estado})"