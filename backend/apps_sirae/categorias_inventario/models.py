from django.db import models


class CategoriaInventario(models.Model):
    id_categoria_inventario = models.AutoField(primary_key=True)
    nombre_categoria = models.CharField(
        max_length=100,
        null=True,
        blank=True
         )

    class Meta:
        db_table = 'categorias_inventario'

    class Meta:
        db_table = 'categorias_inventario'

    def __str__(self):
        return f"Categoria {self.id_categoria_inventario}: {self.nombre_categoria}"