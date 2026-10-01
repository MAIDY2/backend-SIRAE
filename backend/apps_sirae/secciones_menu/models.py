from django.db import models


class SeccionMenu(models.Model):
    id_seccion = models.AutoField(primary_key=True)
    id_jornada = models.ForeignKey(
        'jornadas.Jornada',
        on_delete=models.DO_NOTHING,
        db_column='id_jornada',
        null=True,
        blank=True,
        db_constraint=False
    )
    nombre_seccion = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    def __init__(self, *args, **kwargs):
        legacy_fields = {'id_jornada': 'id_jornada_id'}
        for legacy_name, actual_name in legacy_fields.items():
            if legacy_name in kwargs and actual_name not in kwargs:
                value = kwargs.pop(legacy_name)
                if value is None or isinstance(value, (int, str)):
                    kwargs[actual_name] = value
                else:
                    kwargs[legacy_name] = value
        super().__init__(*args, **kwargs)

    class Meta:
        db_table = 'secciones_menu'
        managed = True
        verbose_name = 'Sección de menú'
        verbose_name_plural = 'Secciones de menú'

    def __str__(self):
        return self.nombre_seccion or f"Sección {self.id_seccion}"

    