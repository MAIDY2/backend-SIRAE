from django.db import models
from apps_sirae.secciones_menu.models import SeccionMenu


class Plato(models.Model):
    id_plato = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150, verbose_name="Nombre del plato")
    descripcion = models.TextField(null=True, blank=True, verbose_name="Descripción")
    precio = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Precio / Costo")
    id_seccion_menu = models.ForeignKey(
        SeccionMenu,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='platos',
        db_column='id_seccion_menu',
        verbose_name="Sección del Menú"
    )
    imagen = models.CharField(max_length=255, null=True, blank=True, verbose_name="URL o ruta de imagen")
    activo = models.BooleanField(default=True, verbose_name="¿Está activo?")

    class Meta:
        db_table = 'platos'
        verbose_name = 'Plato'
        verbose_name_plural = 'Platos'

    def __str__(self):
        return self.nombre