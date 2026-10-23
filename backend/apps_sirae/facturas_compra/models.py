from django.db import models
from django.conf import settings
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.unidades_medida.models import UnidadMedida


class FacturaCompra(models.Model):
    ESTADOS = [
        ('REGISTRADA', 'Registrada'),
        ('ANULADA', 'Anulada'),
    ]

    id_factura = models.AutoField(primary_key=True)
    numero_factura = models.CharField(max_length=100, unique=True)
    proveedor = models.CharField(max_length=150)
    fecha_compra = models.DateField()
    soporte_digital = models.CharField(max_length=255, null=True, blank=True)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='REGISTRADA')

    # Auditoría de anulación
    motivo_anulacion = models.TextField(null=True, blank=True)
    id_usuario_anulacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_usuario_anulacion',
        related_name='facturas_anuladas'
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True)

    # Auditoría de registro
    id_usuario_registro = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_usuario_registro',
        related_name='facturas_registradas'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'facturas_compra'
        ordering = ['-fecha_compra', '-id_factura']

    def __str__(self):
        return f"Factura {self.numero_factura} - {self.proveedor} ({self.estado})"


class DetalleFacturaCompra(models.Model):
    id_detalle = models.AutoField(primary_key=True)
    id_factura = models.ForeignKey(
        FacturaCompra,
        on_delete=models.CASCADE,
        db_column='id_factura',
        related_name='detalles'
    )
    id_ingrediente = models.ForeignKey(
        Ingrediente,
        on_delete=models.RESTRICT,
        db_column='id_ingrediente',
        related_name='detalles_factura'
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    # Control de perecederos
    numero_lote = models.CharField(max_length=100, null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'detalle_factura_compra'

    def __str__(self):
        ing = self.id_ingrediente.nombre_ingrediente if self.id_ingrediente else 'Ingrediente'
        return f"Detalle {self.id_detalle}: {ing} ({self.cantidad})"


class InventarioCentral(models.Model):
    id_inventario_central = models.AutoField(primary_key=True)
    id_ingrediente = models.OneToOneField(
        Ingrediente,
        on_delete=models.RESTRICT,
        db_column='id_ingrediente',
        related_name='inventario_central'
    )
    cantidad_disponible = models.DecimalField(max_digits=10, decimal_places=3, default=0.000)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=3, default=0.000)
    id_unidad_medida = models.ForeignKey(
        UnidadMedida,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        db_column='id_unidad_medida',
        related_name='inventarios_central'
    )
    fecha_ultima_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventario_central'
        ordering = ['id_inventario_central']

    def __str__(self):
        ing = self.id_ingrediente.nombre_ingrediente if self.id_ingrediente else 'Ingrediente'
        return f"Inventario Central - {ing}: {self.cantidad_disponible}"


class Proveedor(models.Model):
    id_proveedor = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=150, unique=True)
    nit = models.CharField(max_length=50, blank=True, null=True)
    telefono = models.CharField(max_length=50, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)
    correo = models.EmailField(max_length=100, blank=True, null=True)
    contacto = models.CharField(max_length=100, blank=True, null=True)
    estado = models.CharField(max_length=20, default='ACTIVO')

    class Meta:
        db_table = 'proveedores'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.nit})" if self.nit else self.nombre
