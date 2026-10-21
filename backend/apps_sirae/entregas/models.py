from django.conf import settings
from django.db import models


class Entrega(models.Model):
    ESTADOS = [
        ('EN_TRANSITO', 'En tránsito'),
        ('RECIBIDA', 'Recibida Conforme'),
        ('CON_NOVEDAD', 'Recibida con Novedad'),
        ('RECHAZADA', 'Rechazada Totalmente'),
    ]

    id_entrega = models.AutoField(primary_key=True)
    id_ingrediente = models.IntegerField()
    id_usuario_supervisor = models.IntegerField()
    id_tipo_mercado = models.IntegerField()
    fecha_entrega = models.DateField()
    fecha_vencimiento = models.DateField()
    cantidad = models.DecimalField(max_digits=10, decimal_places=2)
    observaciones = models.TextField(blank=True)
    frecuencia = models.CharField(max_length=20, blank=True, default='')
    unidad = models.CharField(max_length=30, blank=True, default='')

    id_institucion = models.ForeignKey(
        'instituciones.Institucion',
        on_delete=models.RESTRICT,
        db_column='id_institucion',
        null=True,
        blank=True,
        related_name='entregas'
    )
    id_sede = models.ForeignKey(
        'sedes.Sede',
        on_delete=models.RESTRICT,
        db_column='id_sede',
        null=True,
        blank=True,
        related_name='entregas'
    )

    estado = models.CharField(max_length=30, choices=ESTADOS, default='EN_TRANSITO')
    cantidad_recibida = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cantidad_rechazada = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    motivo_rechazo = models.TextField(blank=True, default='')

    id_usuario_receptor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_usuario_receptor',
        related_name='entregas_recibidas'
    )
    fecha_recepcion = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'entregas'

    def __str__(self):
        return f"Entrega {self.id_entrega} - Ingrediente {self.id_ingrediente} ({self.estado})"