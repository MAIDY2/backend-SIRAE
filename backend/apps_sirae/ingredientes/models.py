from django.db import models


class Ingrediente(models.Model):
    objects = models.Manager()

    TIPO_CONSERVACION_CHOICES = [
        ('perecedero', 'Perecedero'),
        ('no_perecedero', 'No perecedero'),
    ]

    id_ingrediente = models.AutoField(primary_key=True)

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
        max_length=100,
        null=True,
        blank=True
    )

    id_categoria_inventario = models.ForeignKey(
        'categorias_inventario.CategoriaInventario',
        on_delete=models.DO_NOTHING,
        db_column='id_categoria_inventario',
        null=True,
        blank=True,
        db_constraint=False
    )

    id_unidad_medida = models.ForeignKey(
        'unidades_medida.UnidadMedida',
        on_delete=models.DO_NOTHING,
        db_column='id_unidad_medida',
        null=True,
        blank=True,
        db_constraint=False
    )

    tipo_conservacion = models.CharField(
        max_length=20,
        choices=TIPO_CONSERVACION_CHOICES,
        null=True,
        blank=True,
        db_column='tipo_conservacion'
    )

    id_tipo_mercado = models.ForeignKey(
        'tipos_mercado.TipoMercado',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_tipo_mercado',
        related_name='ingredientes',
        db_constraint=False
    )

    def __init__(self, *args, **kwargs):
        legacy_fields = {
            'id_categoria_inventario': 'id_categoria_inventario_id',
            'id_unidad_medida': 'id_unidad_medida_id',
            'id_tipo_mercado': 'id_tipo_mercado_id',
            'nombre': 'nombre_ingrediente',
            'marca': 'marca_ingrediente',
            'imagen': 'imagen_ingrediente',
        }
        for legacy_name, actual_name in legacy_fields.items():
            if legacy_name in kwargs and actual_name not in kwargs:
                value = kwargs.pop(legacy_name)
                if legacy_name in ('nombre', 'marca', 'imagen'):
                    kwargs[actual_name] = value
                elif value is None or isinstance(value, (int, str)):
                    kwargs[actual_name] = value
                else:
                    kwargs[legacy_name] = value
        super().__init__(*args, **kwargs)

    @property
    def nombre(self):
        return self.nombre_ingrediente

    @nombre.setter
    def nombre(self, value):
        self.nombre_ingrediente = value

    @property
    def marca(self):
        return self.marca_ingrediente

    @marca.setter
    def marca(self, value):
        self.marca_ingrediente = value

    class Meta:
        db_table = 'ingredientes'
        managed = True

    def __str__(self):
        return self.nombre_ingrediente or ''
