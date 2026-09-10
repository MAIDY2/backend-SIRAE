from django.db import models


class SeccionMenu(models.Model):
    id_seccion_menu = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True, verbose_name="Nombre de la sección")
    descripcion = models.TextField(null=True, blank=True, verbose_name="Descripción")
    activo = models.BooleanField(default=True, verbose_name="¿Está activo?")

    class Meta:
        db_table = 'secciones_menu'
        verbose_name = 'Sección de Menú'
        verbose_name_plural = 'Secciones de Menú'

    def __str__(self):
        return self.nombre