from rest_framework import serializers

from ..models import Contrato


class ContratoSerializer(serializers.ModelSerializer):
    institucion_nombre = serializers.CharField(source='id_institucion.nombre_institucion', read_only=True)
    sede_nombre = serializers.CharField(source='id_sede.nombre_sede', read_only=True)
    jornada_nombre = serializers.CharField(source='id_jornada.nombre_jornada', read_only=True)
    supervisor_nombre = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Contrato
        fields = [
            "id_contrato",
            "numero_cor",
            "institucion",
            "zona",
            "fecha_inicio",
            "fecha_fin",
            "estado",
            "id_institucion",
            "institucion_nombre",
            "id_sede",
            "sede_nombre",
            "id_jornada",
            "jornada_nombre",
            "cupos",
            "periodicidad_perecederos",
            "dias_cobertura_perecederos",
            "periodicidad_no_perecederos",
            "dias_cobertura_no_perecederos",
            "id_usuario_supervisor",
            "supervisor_nombre",
        ]

    def validate(self, attrs):
        if not attrs.get('id_institucion') and attrs.get('institucion'):
            from apps_sirae.instituciones.models import Institucion
            nombre_inst = str(attrs.get('institucion') or '').strip()
            if nombre_inst:
                inst_obj = (
                    Institucion.objects.filter(nombre_institucion__iexact=nombre_inst).first()
                    or Institucion.objects.filter(nombre_institucion__icontains=nombre_inst).first()
                )
                if inst_obj:
                    attrs['id_institucion'] = inst_obj

        institucion_obj = attrs.get('id_institucion') if 'id_institucion' in attrs else getattr(self.instance, 'id_institucion', None)
        nombre_inst = str(
            attrs.get('institucion') if 'institucion' in attrs else (getattr(self.instance, 'institucion', '') or '')
        ).strip()

        if institucion_obj is not None or nombre_inst:
            qs_existente = Contrato.objects.all()
            if self.instance is not None:
                qs_existente = qs_existente.exclude(pk=self.instance.pk)

            duplicado = None
            if institucion_obj is not None:
                duplicado = qs_existente.filter(id_institucion=institucion_obj).first()
            if duplicado is None and nombre_inst:
                duplicado = qs_existente.filter(institucion__iexact=nombre_inst).first()

            if duplicado is not None:
                num = duplicado.numero_cor or f"ID {duplicado.id_contrato}"
                raise serializers.ValidationError({
                    'id_institucion': (
                        f"Esta institución ya tiene un contrato registrado ({num}). "
                        "Solo se permite un contrato por institución; las sedes se gestionan dentro de ese contrato."
                    )
                })

        dias_defecto = Contrato.DIAS_POR_PERIODICIDAD
        for per_field, dias_field in (
            ('periodicidad_perecederos', 'dias_cobertura_perecederos'),
            ('periodicidad_no_perecederos', 'dias_cobertura_no_perecederos'),
        ):
            if per_field in attrs and dias_field not in attrs:
                clave = (attrs.get(per_field) or '').upper()
                if clave in dias_defecto:
                    attrs[dias_field] = dias_defecto[clave]
        return super().validate(attrs)

    def get_supervisor_nombre(self, obj):
        if obj.id_usuario_supervisor:
            return f"{obj.id_usuario_supervisor.nombre} {obj.id_usuario_supervisor.apellido}".strip()
        return None

