from rest_framework import serializers
from ..models import AsignacionInventario, Inventario
from apps_sirae.ingredientes.models import Ingrediente


class InventarioSerializer(serializers.ModelSerializer):
    ingrediente_nombre = serializers.SerializerMethodField(read_only=True)
    categoria_nombre = serializers.SerializerMethodField(read_only=True)
    marca = serializers.SerializerMethodField(read_only=True)
    unidad_medida_nombre = serializers.SerializerMethodField(read_only=True)
    sede_nombre = serializers.CharField(source='id_sede.nombre_sede', read_only=True)
    institucion_nombre = serializers.CharField(source='id_institucion.nombre_institucion', read_only=True)

    class Meta:
        model = Inventario
        fields = [
            'id_inventario',
            'id_sede',
            'sede_nombre',
            'id_institucion',
            'institucion_nombre',
            'id_ingrediente',
            'ingrediente_nombre',
            'categoria_nombre',
            'marca',
            'unidad_medida_nombre',
            'cantidad_actual',
            'stock_minimo',
            'id_unidad_medida',
        ]

    def _get_ingrediente(self, obj):
        if not hasattr(obj, '_cached_ingrediente'):
            obj._cached_ingrediente = Ingrediente.objects.filter(pk=obj.id_ingrediente).first()
        return obj._cached_ingrediente

    def get_ingrediente_nombre(self, obj):
        try:
            ing = self._get_ingrediente(obj)
            return ing.nombre_ingrediente if ing else None
        except Exception:
            return None

    def get_categoria_nombre(self, obj):
        try:
            ing = self._get_ingrediente(obj)
            if ing and ing.id_categoria_inventario:
                return ing.id_categoria_inventario.nombre_categoria
            return None
        except Exception:
            return None

    def get_marca(self, obj):
        try:
            ing = self._get_ingrediente(obj)
            return ing.marca_ingrediente if ing else None
        except Exception:
            return None

    def get_unidad_medida_nombre(self, obj):
        try:
            ing = self._get_ingrediente(obj)
            if ing and ing.id_unidad_medida:
                return ing.id_unidad_medida.nombre
            return None
        except Exception:
            return None


class AsignacionInventarioSerializer(serializers.ModelSerializer):
    institucion_nombre = serializers.CharField(source='id_institucion.nombre_institucion', read_only=True)
    ingrediente_nombre = serializers.CharField(source='id_ingrediente.nombre_ingrediente', read_only=True)
    unidad_medida_nombre = serializers.CharField(source='id_unidad_medida.nombre', read_only=True)
    unidad_medida_abreviatura = serializers.CharField(source='id_unidad_medida.abreviatura', read_only=True)
    contrato_numero = serializers.CharField(source='id_contrato.numero_cor', read_only=True)
    usuario_asignador_nombre = serializers.SerializerMethodField(read_only=True)
    cantidad_pendiente = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = AsignacionInventario
        fields = [
            'id_asignacion',
            'codigo_lote',
            'id_institucion',
            'institucion_nombre',
            'id_contrato',
            'contrato_numero',
            'id_ingrediente',
            'ingrediente_nombre',
            'id_unidad_medida',
            'unidad_medida_nombre',
            'unidad_medida_abreviatura',
            'cantidad_asignada',
            'cantidad_despachada',
            'cantidad_pendiente',
            'periodo_inicio',
            'periodo_fin',
            'estado',
            'observaciones',
            'id_usuario_asignador',
            'usuario_asignador_nombre',
            'fecha_asignacion',
            'fecha_actualizacion',
        ]
        read_only_fields = [
            'id_asignacion',
            'codigo_lote',
            'cantidad_despachada',
            'cantidad_pendiente',
            'id_usuario_asignador',
            'fecha_asignacion',
            'fecha_actualizacion',
        ]

    def get_usuario_asignador_nombre(self, obj):
        u = obj.id_usuario_asignador
        if not u:
            return None
        return f"{u.nombre} {u.apellido}".strip() or u.username
