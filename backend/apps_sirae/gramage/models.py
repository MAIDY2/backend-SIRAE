from django.conf import settings
from django.db import models
from django.utils import timezone

from apps_sirae.grados.models import Grados


class Gramage(models.Model):
    ESTADOS = [
        ('ACTIVO', 'Activo'),
        ('INACTIVO', 'Inactivo'),
    ]

    CONTEXTOS_APLICACION = [
        ('GENERAL', 'General'),
        ('DESAYUNO', 'Desayuno'),
        ('ALMUERZO', 'Almuerzo'),
        ('REFRIGERIO', 'Refrigerio / Complemento'),
        ('RACION_PREPARADA', 'Ración preparada en sitio'),
        ('RACION_INDUSTRIALIZADA', 'Ración industrializada'),
    ]

    id_gramaje = models.AutoField(
        primary_key=True,
        db_column='id_gramaje'
    )

    id_ingrediente = models.ForeignKey(
        'ingredientes.Ingrediente',
        on_delete=models.PROTECT,
        db_column='id_ingrediente',
        null=True,
        blank=True,
        related_name='gramajes'
    )

    id_grado = models.ForeignKey(
        Grados,
        on_delete=models.PROTECT,
        db_column='id_grado',
        null=True,
        blank=True,
        related_name='gramajes'
    )

    id_unidad_medida = models.ForeignKey(
        'unidades_medida.UnidadMedida',
        on_delete=models.PROTECT,
        db_column='id_unidad_medida',
        null=True,
        blank=True,
        related_name='gramajes'
    )

    cantidad_gramaje = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        db_column='cantidad_gramaje'
    )

    valor_anterior = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        null=True,
        blank=True,
        db_column='valor_anterior'
    )

    contexto_aplicacion = models.CharField(
        max_length=60,
        choices=CONTEXTOS_APLICACION,
        default='GENERAL'
    )

    descripcion = models.TextField(
        null=True,
        blank=True,
        default=''
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='ACTIVO'
    )

    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    id_usuario_modificacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_usuario_modificacion',
        related_name='gramajes_modificados'
    )

    class Meta:
        db_table = 'gramajes'
        managed = True
        ordering = ['id_gramaje']

    def __str__(self):
        ing_nom = self.id_ingrediente.nombre_ingrediente if self.id_ingrediente_id else "Sin producto"
        grado_nom = self.id_grado.nombre_grado if self.id_grado_id else "Sin grado"
        return f"Gramaje {self.id_gramaje} - {ing_nom} ({grado_nom}): {self.cantidad_gramaje}"

    # Alias de compatibilidad hacia atrás (con 'g')
    @property
    def id_gramage(self):
        return self.id_gramaje

    @property
    def cantidad_gramage(self):
        return self.cantidad_gramaje

    @cantidad_gramage.setter
    def cantidad_gramage(self, value):
        self.cantidad_gramaje = value


class HistorialGramaje(models.Model):
    """
    Registro histórico inmutable de cambios de cantidad, unidad, contexto o estado de un gramaje.
    """
    TIPOS_EVENTO = [
        ('CREACION', 'Creación'),
        ('EDICION', 'Edición'),
        ('ACTIVACION', 'Activación'),
        ('INACTIVACION', 'Inactivación'),
    ]

    id_historial_gramaje = models.AutoField(primary_key=True)
    id_gramaje = models.ForeignKey(
        Gramage,
        on_delete=models.PROTECT,
        db_column='id_gramaje',
        related_name='historial'
    )
    tipo_evento = models.CharField(max_length=20, choices=TIPOS_EVENTO, default='EDICION')
    cantidad_anterior = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    cantidad_nueva = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)
    unidad_anterior = models.CharField(max_length=60, blank=True, default='')
    unidad_nueva = models.CharField(max_length=60, blank=True, default='')
    estado_anterior = models.CharField(max_length=20, blank=True, default='')
    estado_nuevo = models.CharField(max_length=20, blank=True, default='')
    contexto_anterior = models.CharField(max_length=60, blank=True, default='')
    contexto_nuevo = models.CharField(max_length=60, blank=True, default='')
    observaciones = models.TextField(blank=True, default='')
    id_usuario_modificacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_usuario_modificacion',
        related_name='historial_gramajes_registrados'
    )
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'historial_gramajes'
        ordering = ['-fecha_cambio', '-id_historial_gramaje']

    def __str__(self):
        return f"Historial Gramaje #{self.id_gramaje_id} ({self.tipo_evento})"