from django.db import models


class Contrato(models.Model):
    id_contrato = models.AutoField(primary_key=True)
    numero_cor = models.CharField(max_length=100, null=True, blank=True)
    institucion = models.CharField(max_length=150, null=True, blank=True)
    zona = models.CharField(max_length=100, null=True, blank=True)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'contrato_pae'
        managed = False

    def __str__(self):
        return f"Contrato {self.numero_cor} - {self.institucion} ({self.estado})"