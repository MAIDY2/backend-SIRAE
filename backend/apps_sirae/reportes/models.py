from django.conf import settings
from django.db import models
from django.utils import timezone


class PlantillaOficial(models.Model):
    """
    SIR-170: Catálogo de plantillas oficiales parametrizables por proceso del PAE.
    La definición versionada de secciones, campos, tablas, fórmulas y conversiones
    reside en PlantillaVersion para preservar el historial sin alteración retroactiva.
    """

    PROCESO_CHOICES = [
        ('REMISION', 'Remisión de alimentos y víveres'),
        ('RECEPCION', 'Recepción y verificación de alimentos'),
        ('INVENTARIO', 'Control de inventario y kárdex'),
        ('ASISTENCIA', 'Registro de asistencia diaria'),
        ('PREPARACION', 'Preparación de alimentos y minutas'),
        ('CONSUMO', 'Consumo y balance operativo PAE'),
        ('MINUTA', 'Minuta y programación de menús'),
        ('OTRO', 'Otro formato oficial PAE'),
    ]

    id_plantilla = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=60, unique=True)
    nombre = models.CharField(max_length=160)
    descripcion = models.TextField(blank=True, default='')
    categoria_proceso = models.CharField(
        max_length=30,
        choices=PROCESO_CHOICES,
        default='REMISION',
    )
    finalidad = models.TextField(blank=True, default='')
    roles_autorizados = models.JSONField(default=list)
    activa = models.BooleanField(default=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plantillas_pae_creadas',
    )
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reportes_plantillas_oficiales'
        ordering = ['categoria_proceso', 'nombre', 'id_plantilla']

    def __str__(self):
        return f"{self.codigo} - {self.nombre} ({self.categoria_proceso})"


class PlantillaVersion(models.Model):
    """
    SIR-170: Versión específica de una plantilla oficial.
    Solo puede editarse en estado BORRADOR; una vez PUBLICADA o referenciada por una
    PlanillaGenerada es estrictamente inmutable.
    """

    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PUBLICADA', 'Publicada'),
        ('ARCHIVADA', 'Archivada'),
    ]

    id_version = models.AutoField(primary_key=True)
    id_plantilla = models.ForeignKey(
        PlantillaOficial,
        on_delete=models.CASCADE,
        db_column='id_plantilla',
        related_name='versiones',
    )
    numero_version = models.PositiveIntegerField(default=1)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='BORRADOR',
    )
    esquema = models.JSONField(default=dict)
    notas_version = models.TextField(blank=True, default='')
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='versiones_plantilla_creadas',
    )
    publicado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='versiones_plantilla_publicadas',
    )
    fecha_creacion = models.DateTimeField(default=timezone.now)
    fecha_publicacion = models.DateTimeField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reportes_plantillas_versiones'
        ordering = ['id_plantilla_id', '-numero_version']
        constraints = [
            models.UniqueConstraint(
                fields=['id_plantilla', 'numero_version'],
                name='uniq_reporte_plantilla_version_num',
            )
        ]

    def es_inmutable(self) -> bool:
        return self.estado != 'BORRADOR' or self.planillas_generadas.exists()

    def __str__(self):
        return f"{self.id_plantilla.codigo} v{self.numero_version} ({self.estado})"


class PlanillaGenerada(models.Model):
    """
    SIR-171 & SIR-172: Documento/planilla auto-diligenciada a partir de una versión
    publicada de plantilla y de los registros reales de SIRAE.
    """

    ESTADO_CHOICES = [
        ('BORRADOR', 'Borrador'),
        ('PENDIENTE', 'Pendiente'),
        ('OBSERVADO', 'Observado'),
        ('VALIDADO', 'Validado'),
        ('CERRADO', 'Cerrado'),
    ]

    id_planilla = models.AutoField(primary_key=True)
    codigo_documento = models.CharField(max_length=60, unique=True)
    id_plantilla_version = models.ForeignKey(
        PlantillaVersion,
        on_delete=models.PROTECT,
        db_column='id_plantilla_version',
        related_name='planillas_generadas',
    )
    nombre_documento = models.CharField(max_length=200)
    categoria_proceso = models.CharField(max_length=30, db_index=True)
    id_institucion = models.ForeignKey(
        'instituciones.Institucion',
        on_delete=models.PROTECT,
        db_column='id_institucion',
        related_name='planillas_generadas',
    )
    id_sede = models.ForeignKey(
        'sedes.Sede',
        on_delete=models.PROTECT,
        db_column='id_sede',
        null=True,
        blank=True,
        related_name='planillas_generadas',
    )
    id_contrato = models.ForeignKey(
        'contratos_pae.Contrato',
        on_delete=models.SET_NULL,
        db_column='id_contrato',
        null=True,
        blank=True,
        related_name='planillas_generadas',
    )
    id_jornada = models.ForeignKey(
        'jornadas.Jornada',
        on_delete=models.SET_NULL,
        db_column='id_jornada',
        null=True,
        blank=True,
        db_constraint=False,
        related_name='planillas_generadas',
    )
    periodo = models.CharField(max_length=80)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    clave_unicidad = models.CharField(max_length=255, unique=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADO_CHOICES,
        default='BORRADOR',
    )
    evento_origen = models.CharField(max_length=80, default='GENERACION_AUTOMATICA')
    responsable_generacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planillas_generadas',
    )
    responsable_nombre = models.CharField(max_length=200, blank=True, default='')
    contenido_snapshot = models.JSONField(default=dict)
    valores_manuales = models.JSONField(default=dict)
    campos_pendientes = models.JSONField(default=list)
    registros_origen = models.JSONField(default=dict)
    observaciones = models.TextField(blank=True, default='')
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='planillas_revisadas',
    )
    fecha_revision = models.DateTimeField(null=True, blank=True)
    fecha_generacion = models.DateTimeField(default=timezone.now)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'reportes_planillas_generadas'
        ordering = ['-fecha_generacion', '-id_planilla']

    def __str__(self):
        return f"{self.codigo_documento} | {self.nombre_documento} ({self.estado})"

