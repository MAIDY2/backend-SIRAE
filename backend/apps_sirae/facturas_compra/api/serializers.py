from rest_framework import serializers
from ..models import FacturaCompra, DetalleFacturaCompra, InventarioCentral


class DetalleFacturaCompraSerializer(serializers.ModelSerializer):
    ingrediente_nombre = serializers.CharField(source='id_ingrediente.nombre_ingrediente', read_only=True)
    categoria_nombre = serializers.CharField(
        source='id_ingrediente.id_categoria_inventario.nombre_categoria',
        read_only=True
    )
    unidad_medida_nombre = serializers.CharField(
        source='id_ingrediente.id_unidad_medida.nombre',
        read_only=True
    )
    tipo_conservacion = serializers.CharField(
        source='id_ingrediente.tipo_conservacion',
        read_only=True
    )

    class Meta:
        model = DetalleFacturaCompra
        fields = [
            'id_detalle',
            'id_factura',
            'id_ingrediente',
            'ingrediente_nombre',
            'categoria_nombre',
            'unidad_medida_nombre',
            'tipo_conservacion',
            'cantidad',
            'precio_unitario',
            'subtotal',
            'numero_lote',
            'fecha_vencimiento',
        ]
        read_only_fields = ['id_detalle', 'id_factura']


class FacturaCompraSerializer(serializers.ModelSerializer):
    detalles = DetalleFacturaCompraSerializer(many=True, required=False)
    usuario_registro_nombre = serializers.SerializerMethodField(read_only=True)
    usuario_anulacion_nombre = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = FacturaCompra
        fields = [
            'id_factura',
            'numero_factura',
            'proveedor',
            'fecha_compra',
            'soporte_digital',
            'valor_total',
            'estado',
            'motivo_anulacion',
            'id_usuario_anulacion',
            'usuario_anulacion_nombre',
            'fecha_anulacion',
            'id_usuario_registro',
            'usuario_registro_nombre',
            'fecha_creacion',
            'detalles',
        ]
        read_only_fields = [
            'id_factura',
            'estado',
            'motivo_anulacion',
            'id_usuario_anulacion',
            'fecha_anulacion',
            'id_usuario_registro',
            'fecha_creacion',
        ]

    def get_usuario_registro_nombre(self, obj):
        if obj.id_usuario_registro:
            return f"{obj.id_usuario_registro.nombre} {obj.id_usuario_registro.apellido}".strip()
        return None

    def get_usuario_anulacion_nombre(self, obj):
        if obj.id_usuario_anulacion:
            return f"{obj.id_usuario_anulacion.nombre} {obj.id_usuario_anulacion.apellido}".strip()
        return None


class InventarioCentralSerializer(serializers.ModelSerializer):
    ingrediente_nombre = serializers.CharField(source='id_ingrediente.nombre_ingrediente', read_only=True)
    categoria_nombre = serializers.CharField(
        source='id_ingrediente.id_categoria_inventario.nombre_categoria',
        read_only=True
    )
    unidad_medida_nombre = serializers.CharField(
        source='id_unidad_medida.nombre',
        read_only=True
    )
    unidad_medida_abreviatura = serializers.CharField(
        source='id_unidad_medida.abreviatura',
        read_only=True
    )
    tipo_conservacion = serializers.CharField(
        source='id_ingrediente.tipo_conservacion',
        read_only=True
    )

    class Meta:
        model = InventarioCentral
        fields = [
            'id_inventario_central',
            'id_ingrediente',
            'ingrediente_nombre',
            'categoria_nombre',
            'tipo_conservacion',
            'cantidad_disponible',
            'stock_minimo',
            'id_unidad_medida',
            'unidad_medida_nombre',
            'unidad_medida_abreviatura',
            'fecha_ultima_actualizacion',
        ]
        read_only_fields = ['id_inventario_central', 'fecha_ultima_actualizacion']
