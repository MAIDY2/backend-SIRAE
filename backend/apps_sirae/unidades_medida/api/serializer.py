from decimal import Decimal
from rest_framework import serializers
from ..models import EquivalenciaUnidad, UnidadMedida


class UnidadMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadMedida
        fields = [
            'id_unidad_medida',
            'nombre',
            'abreviatura',
            'tipo_magnitud',
            'factor_conversion_base',
            'estado',
        ]

    def validate_factor_conversion_base(self, value):
        if value is None or Decimal(str(value)) <= 0:
            raise serializers.ValidationError(
                'El factor de conversión base debe ser mayor a cero (0).'
            )
        return value

    def validate_nombre(self, value):
        nombre = (value or '').strip()
        if not nombre:
            raise serializers.ValidationError('El nombre de la unidad es obligatorio.')
        qs = UnidadMedida.objects.filter(nombre__iexact=nombre)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(f"Ya existe una unidad de medida llamada '{nombre}'.")
        return nombre


class EquivalenciaUnidadSerializer(serializers.ModelSerializer):
    ingrediente_nombre = serializers.CharField(source='id_ingrediente.nombre_ingrediente', read_only=True)
    unidad_origen_nombre = serializers.CharField(source='id_unidad_origen.nombre', read_only=True)
    unidad_origen_abreviatura = serializers.CharField(source='id_unidad_origen.abreviatura', read_only=True)
    unidad_origen_magnitud = serializers.CharField(source='id_unidad_origen.tipo_magnitud', read_only=True)
    unidad_destino_nombre = serializers.CharField(source='id_unidad_destino.nombre', read_only=True)
    unidad_destino_abreviatura = serializers.CharField(source='id_unidad_destino.abreviatura', read_only=True)
    unidad_destino_magnitud = serializers.CharField(source='id_unidad_destino.tipo_magnitud', read_only=True)

    class Meta:
        model = EquivalenciaUnidad
        fields = [
            'id_equivalencia',
            'id_ingrediente',
            'ingrediente_nombre',
            'id_unidad_origen',
            'unidad_origen_nombre',
            'unidad_origen_abreviatura',
            'unidad_origen_magnitud',
            'id_unidad_destino',
            'unidad_destino_nombre',
            'unidad_destino_abreviatura',
            'unidad_destino_magnitud',
            'factor_conversion',
            'observaciones',
            'estado',
            'fecha_actualizacion',
        ]

    def validate(self, attrs):
        ing = attrs.get('id_ingrediente') or getattr(self.instance, 'id_ingrediente', None)
        u_ori = attrs.get('id_unidad_origen') or getattr(self.instance, 'id_unidad_origen', None)
        u_des = attrs.get('id_unidad_destino') or getattr(self.instance, 'id_unidad_destino', None)
        factor = attrs.get('factor_conversion') if 'factor_conversion' in attrs else getattr(self.instance, 'factor_conversion', None)
        estado = attrs.get('estado') or getattr(self.instance, 'estado', 'ACTIVO')

        if not ing or not u_ori or not u_des:
            raise serializers.ValidationError(
                'El producto, la unidad de origen y la unidad de destino son obligatorios.'
            )

        if u_ori.pk == u_des.pk:
            raise serializers.ValidationError(
                'La unidad de origen y la unidad de destino deben ser diferentes.'
            )

        if factor is None or Decimal(str(factor)) <= 0:
            raise serializers.ValidationError({
                'factor_conversion': 'El factor de conversión debe ser mayor a cero (0).'
            })

        if estado == 'ACTIVO':
            dup = EquivalenciaUnidad.objects.filter(
                id_ingrediente=ing,
                id_unidad_origen=u_ori,
                id_unidad_destino=u_des,
                estado='ACTIVO',
            )
            if self.instance:
                dup = dup.exclude(pk=self.instance.pk)
            if dup.exists():
                raise serializers.ValidationError(
                    'Ya existe una equivalencia técnica activa para este producto y este par de unidades.'
                )

        return super().validate(attrs)
