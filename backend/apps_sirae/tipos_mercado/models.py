from django.db import models

class TipoMercado(models.Model):
    id_tipo_mercado = models.AutoField(primary_key=True)
    nombre_tipo = models.CharField(max_length=50)

    class Meta:
        db_table = 'tipos_mercado'

    def __str__(self):
        return self.nombre_tipo