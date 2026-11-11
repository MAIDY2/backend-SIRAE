from django.conf import settings
from django.db import models


NIVELES_EDUCATIVOS_CHOICES = [
    ('PREESCOLAR', 'Preescolar'),
    ('PRIMARIA', 'Primaria'),
    ('SECUNDARIA', 'Secundaria'),
    ('MEDIA', 'Media'),
    ('OTRO', 'Otro'),
]

ESTADOS_CATALOGO_CHOICES = [
    ('ACTIVO', 'Activo'),
    ('INACTIVO', 'Inactivo'),
]


class GrupoGramaje(models.Model):
    """
    Agrupación de grados escolares por nivel educativo para parametrizar y calcular gramajes PAE.
    """
    NIVELES_EDUCATIVOS = NIVELES_EDUCATIVOS_CHOICES
    ESTADOS = ESTADOS_CATALOGO_CHOICES

    id_grupo_gramaje = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=120, unique=True)
    nivel_educativo = models.CharField(
        max_length=20,
        choices=NIVELES_EDUCATIVOS,
        default='PRIMARIA',
    )
    descripcion = models.TextField(blank=True, default='')
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='ACTIVO',
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'grupos_gramaje'
        ordering = ['id_grupo_gramaje']

    def __str__(self):
        return f"{self.nombre} ({self.get_nivel_educativo_display()})"


class Grados(models.Model):
    NIVELES_EDUCATIVOS = NIVELES_EDUCATIVOS_CHOICES
    ESTADOS = ESTADOS_CATALOGO_CHOICES

    id_grado = models.AutoField(primary_key=True)
    nombre_grado = models.CharField(max_length=100)
    id_grupo_gramaje = models.ForeignKey(
        GrupoGramaje,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column='id_grupo_gramaje',
        related_name='grados',
    )
    nivel_educativo = models.CharField(
        max_length=20,
        choices=NIVELES_EDUCATIVOS,
        default='PRIMARIA',
    )
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='ACTIVO',
    )
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nombre_grado

    class Meta:
        db_table = 'grados'
        managed = True  # Cambiado a True para que Django gestione la tabla
        ordering = ['id_grado']


class HistorialClasificacionGrado(models.Model):
    """
    Bitácora inmutable de cambios en la clasificación de un grado (grupo de gramaje y nivel educativo)
    para conservar trazabilidad de periodos anteriores.
    """
    id_historial_clasificacion = models.AutoField(primary_key=True)
    id_grado = models.ForeignKey(
        Grados,
        on_delete=models.PROTECT,
        db_column='id_grado',
        related_name='historial_clasificacion',
    )
    grupo_anterior = models.ForeignKey(
        GrupoGramaje,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_grupo_anterior',
        related_name='historiales_como_anterior',
    )
    grupo_nuevo = models.ForeignKey(
        GrupoGramaje,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_grupo_nuevo',
        related_name='historiales_como_nuevo',
    )
    nombre_grupo_anterior = models.CharField(max_length=120, blank=True, default='')
    nombre_grupo_nuevo = models.CharField(max_length=120, blank=True, default='')
    nivel_anterior = models.CharField(max_length=20, blank=True, default='')
    nivel_nuevo = models.CharField(max_length=20, blank=True, default='')
    motivo = models.CharField(max_length=255, blank=True, default='')
    id_usuario_modificacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_usuario_modificacion',
        related_name='cambios_clasificacion_grado',
    )
    fecha_cambio = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'historial_clasificacion_grados'
        ordering = ['-fecha_cambio', '-id_historial_clasificacion']

    def __str__(self):
        return f"{self.id_grado.nombre_grado}: {self.nombre_grupo_anterior or 'Sin grupo'} -> {self.nombre_grupo_nuevo or 'Sin grupo'}"