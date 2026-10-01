from django.db import models


class Plato(models.Model):
    id_plato = models.AutoField(primary_key=True)
    id_seccion = models.ForeignKey(
        'secciones_menu.SeccionMenu',
        on_delete=models.DO_NOTHING,
        db_column='id_seccion',
        null=True,
        blank=True,
        db_constraint=False
    )
    nombre_plato = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )
    componente = models.CharField(
        max_length=50,
        null=True,
        blank=True
    )

    def __init__(self, *args, **kwargs):
        if 'id_seccion' in kwargs and 'id_seccion_id' not in kwargs:
            value = kwargs.pop('id_seccion')
            if value is None or isinstance(value, (int, str)):
                kwargs['id_seccion_id'] = value
            else:
                kwargs['id_seccion'] = value
        super().__init__(*args, **kwargs)

    class Meta:
        db_table = 'platos'
        managed = True
        verbose_name = 'Plato'
        verbose_name_plural = 'Platos'

    def __str__(self):
        return self.nombre_plato or f"Plato {self.id_plato}"