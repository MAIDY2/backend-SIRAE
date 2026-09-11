from django.db import models


class Ingrediente(models.Model):
    id_ingrediente = models.AutoField(primary_key=True)


    id_categoria_inventario = models.ForeignKey(
        'categorias_inventario.CategoriaInventario',
        on_delete=models.DO_NOTHING,
        db_column='id_categoria_inventario',
        null=True,
        blank=True
    )

    id_unidad_medida = models.ForeignKey(
        'unidades_medida.UnidadMedida',
        on_delete=models.DO_NOTHING,
        db_column='id_unidad_medida',
        null=True,
        blank=True
    )


    nombre_ingrediente = models.CharField(max_length=100, null=True, blank=True)
    descripcion = models.TextField( null=True, blank=True)
    imagen_ingrediente = models.CharField(max_length=255, null=True, blank=True)
    marca_ingrediente = models.CharField( null=True, blank=True) 

    class Meta:
            db_table = 'ingredientes'


    def __str__(self):
        return self.nombre_ingrediente