from django.db import models


class SeccionMenu(models.Model):
    id_seccion = models.AutoField(primary_key=True)
    id_jornada = models.IntegerField(null=True, blank=True)
    nombre_seccion = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.nombre_seccion if self.nombre_seccion else f"Sección {self.id_seccion}"

    class Meta:
        db_table = 'secciones_menu'

    id_jornada = models.ForeignKey(
        'jornadas.Jornada',
        on_delete=models.DO_NOTHING,
        db_column='id_jornada',
        null=True,
        blank=True
    )

    nombre_seccion = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    class Meta:
        db_table = 'secciones_menu'
        verbose_name = 'Sección de menú'
        verbose_name_plural = 'Secciones de menú'

    def __str__(self):
        return self.nombre_seccion or ''
