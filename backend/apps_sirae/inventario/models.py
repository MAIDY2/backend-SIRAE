from django.db import models


class CategoriaInventario(models.Model):
    id_categoria_inventario = models.AutoField(primary_key=True)
    nombre_categoria = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.nombre_categoria

    class Meta:
        managed = False
        db_table = 'categorias_inventario'


class UnidadMedida(models.Model):
    id_unidad_medida = models.AutoField(primary_key=True)
    nombre = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )
    abreviatura = models.CharField(
        max_length=10,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.nombre

    class Meta:
        managed = False
        db_table = 'unidades_medida'


class Ingrediente(models.Model):
    id_ingrediente = models.AutoField(primary_key=True)

    id_categoria_inventario = models.ForeignKey(
        CategoriaInventario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_categoria_inventario'
    )

    id_unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_unidad_medida'
    )

    nombre_ingrediente = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    descripcion = models.TextField(
        null=True,
        blank=True
    )

    imagen_ingrediente = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    marca_ingrediente = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    def __str__(self):
        return self.nombre_ingrediente

    class Meta:
        managed = False
        db_table = 'ingredientes'


class Inventario(models.Model):
    id_inventario = models.AutoField(primary_key=True)

    # CORREGIDO: id_ingrediente
    id_ingrediente = models.ForeignKey(
        Ingrediente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_ingrediente'
    )

    cantidad_actual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    stock_minimo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )

    id_unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_unidad_medida'
    )

    def __str__(self):
        return f"Inventario {self.id_inventario}"

    class Meta:
        managed = False
        db_table = 'inventario'


class MovimientoInventario(models.Model):
    id_movimiento_inventario = models.AutoField(primary_key=True)

    id_ingrediente = models.ForeignKey(
        Ingrediente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_ingrediente'
    )

    id_usuario_manipuladora = models.IntegerField(
        null=True,
        blank=True,
        db_column='id_usuario_manipuladora'
    )

    tipo_movimiento = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    fecha = models.DateTimeField(
        null=True,
        blank=True
    )

    cantidad = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )

    observaciones = models.TextField(
        null=True,
        blank=True
    )

    id_unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_unidad_medida'
    )

    def __str__(self):
        return f"Movimiento {self.id_movimiento_inventario}"

    class Meta:
        managed = False
        db_table = 'movimientos_inventario'
