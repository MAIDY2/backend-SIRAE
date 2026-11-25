from django.db import transaction
from django.shortcuts import get_object_or_404

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..models import Contrato, DistribucionSede, DistribucionGrado
from .serializer import ContratoSerializer
from apps_sirae.grados.models import Grados
from apps_sirae.jornadas.models import Jornada
from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
from apps_sirae.sedes.models import Sede
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class ContratoViewSet(ModelViewSet):
    serializer_class = ContratoSerializer
    queryset = Contrato.objects.all().order_by('-id_contrato')
    permission_classes = [IsSuperAdminOrReadOnly]
    pagination_class = None

    def perform_create(self, serializer):
        contrato = serializer.save()
        try:
            from django.db.models import Q
            from apps_sirae.notificaciones.models import Notificacion
            from apps_sirae.usuarios.models import Usuario

            remitente_id = self.request.user.id_usuario if (self.request.user and self.request.user.is_authenticated) else None
            num_contrato = contrato.numero_contrato or f"CTO-{contrato.id_contrato}"
            valor_fmt = f"${contrato.valor_total:,.2f}" if contrato.valor_total else "$0.00"

            destinatarios = Usuario.objects.filter(
                is_active=True
            ).filter(
                Q(rol__nombre__icontains='admin') | Q(is_superuser=True)
            )

            for u in destinatarios:
                Notificacion.objects.create(
                    id_usuario=u.id_usuario,
                    id_remitente=remitente_id,
                    titulo=f"📋 Contrato PAE registrado: {num_contrato}",
                    mensaje=f"Se ha registrado el contrato PAE '{num_contrato}'. Presupuesto: {valor_fmt}. Vigencia hasta {contrato.fecha_fin}.",
                )
        except Exception:
            pass

    # ──────────────────────────────────────────
    # GET  /api/contratos/{id}/distribucion/
    # PUT  /api/contratos/{id}/distribucion/
    # ──────────────────────────────────────────
    @action(
        detail=True,
        methods=['get', 'put'],
        url_path='distribucion',
        permission_classes=[IsSuperAdminOrReadOnly],
    )
    def distribucion(self, request, pk=None):
        contrato = get_object_or_404(Contrato, pk=pk)

        if request.method == 'GET':
            return self._get_distribucion(contrato)
        return self._put_distribucion(request, contrato)

    # ── Lectura ───────────────────────────────
    def _get_distribucion(self, contrato):
        """Devuelve la distribución de cupos actual del contrato."""
        sedes_data = []

        for dist_sede in (
            DistribucionSede.objects
            .filter(id_contrato=contrato)
            .select_related('id_sede')
            .prefetch_related('grados__id_grado')
        ):
            grados_data = [
                {
                    'id_grado': dg.id_grado.id_grado,
                    'nombre': dg.id_grado.nombre_grado,
                    'nombre_grado': dg.id_grado.nombre_grado,
                    'cupos': dg.cupos_asignados,
                    'cuposAsignados': dg.cupos_asignados,
                    'cupos_asignados': dg.cupos_asignados,
                }
                for dg in dist_sede.grados.select_related('id_grado').all()
            ]
            # Buscar jornadas vinculadas a esta sede
            sj_list = SedeJornada.objects.filter(id_sede=dist_sede.id_sede).select_related('id_jornada')
            jornadas_nombres = [sj.id_jornada.nombre_jornada for sj in sj_list if sj.id_jornada]
            tiene_manana = any('mañan' in j.lower() for j in jornadas_nombres)
            tiene_tarde = any('tard' in j.lower() for j in jornadas_nombres)

            sedes_data.append({
                'id_sede': dist_sede.id_sede.id_sede,
                'nombre_sede': dist_sede.id_sede.nombre_sede,
                'cupos': dist_sede.cupos_asignados,
                'cupos_asignados': dist_sede.cupos_asignados,
                'cuposAsignados': dist_sede.cupos_asignados,
                'jornada_manana': tiene_manana,
                'jornada_tarde': tiene_tarde,
                'jornadas': jornadas_nombres,
                'grados': grados_data,
            })

        # Si existen sedes vinculadas a la institución del contrato que aún no están en DistribucionSede, incluirlas
        ids_incluidas = {s['id_sede'] for s in sedes_data}
        inst_id = contrato.id_institucion_id
        if not inst_id and contrato.institucion:
            from apps_sirae.instituciones.models import Institucion
            inst_obj = Institucion.objects.filter(
                nombre_institucion__iexact=contrato.institucion.strip()
            ).first()
            if inst_obj:
                inst_id = inst_obj.id_institucion
        if inst_id:
            for sede_extra in Sede.objects.filter(id_institucion_id=inst_id).order_by('id_sede'):
                if sede_extra.id_sede not in ids_incluidas:
                    sj_list = SedeJornada.objects.filter(id_sede=sede_extra).select_related('id_jornada')
                    jornadas_nombres = [sj.id_jornada.nombre_jornada for sj in sj_list if sj.id_jornada]
                    sedes_data.append({
                        'id_sede': sede_extra.id_sede,
                        'nombre_sede': sede_extra.nombre_sede,
                        'cupos': 0,
                        'cupos_asignados': 0,
                        'cuposAsignados': 0,
                        'jornada_manana': any('mañan' in j.lower() for j in jornadas_nombres),
                        'jornada_tarde': any('tard' in j.lower() for j in jornadas_nombres),
                        'jornadas': jornadas_nombres,
                        'grados': [],
                    })

        return Response({
            'contratoId': contrato.id_contrato,
            'cuposAutorizados': contrato.cupos,
            'total_distribuido': sum(s['cuposAsignados'] for s in sedes_data),
            'sedes': sedes_data,
        })

    # ── Escritura ─────────────────────────────
    def _put_distribucion(self, request, contrato):
        """Valida y persiste la nueva distribución de cupos."""
        data = request.data

        # 1. Estructura mínima
        sedes = data.get('sedes')
        if not isinstance(sedes, list):
            return Response(
                {'error': 'El campo "sedes" es obligatorio y debe ser una lista.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 2. Validar negativos y calcular total (soporta camelCase y snake_case)
        total_cupos = 0
        for sede in sedes:
            cupos_raw = sede.get('cuposAsignados') if 'cuposAsignados' in sede else sede.get('cupos_asignados', sede.get('cupos', 0))

            if not isinstance(cupos_raw, (int, float)) or cupos_raw < 0:
                return Response(
                    {'error': f'Cupos de sede {sede.get("id_sede")} no válidos. Deben ser enteros ≥ 0.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            cupos_sede = int(cupos_raw)

            grados = sede.get('grados', [])
            if not isinstance(grados, list):
                return Response(
                    {'error': f'La sede {sede.get("id_sede")} debe incluir una lista "grados".'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            total_grados = 0
            for grado in grados:
                grado_raw = grado.get('cuposAsignados') if 'cuposAsignados' in grado else grado.get('cupos_asignados', grado.get('cupos', 0))
                if not isinstance(grado_raw, (int, float)) or grado_raw < 0:
                    return Response(
                        {
                            'error': (
                                f'Cupos del grado {grado.get("id_grado")} '
                                f'en sede {sede.get("id_sede")} no válidos.'
                            )
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                total_grados += int(grado_raw)

            if total_grados > cupos_sede:
                return Response(
                    {
                        'error': (
                            f'La suma de cupos por grado ({total_grados}) '
                            f'supera los cupos de la sede {sede.get("id_sede")} ({cupos_sede}).'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            total_cupos += cupos_sede

        # 3. Validar contra el tope del contrato
        if total_cupos > contrato.cupos:
            return Response(
                {
                    'error': (
                        f'La distribución total ({total_cupos} cupos) '
                        f'supera los cupos autorizados del contrato ({contrato.cupos}).'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # 4. Persistir (reemplazar distribución completa)
        with transaction.atomic():
            DistribucionSede.objects.filter(id_contrato=contrato).delete()

            jornada_manana_obj = Jornada.objects.filter(nombre_jornada__icontains='mañan').first()
            jornada_tarde_obj = Jornada.objects.filter(nombre_jornada__icontains='tard').first()
            jornada_default = contrato.id_jornada or jornada_manana_obj or Jornada.objects.first()

            for sede in sedes:
                sede_obj = get_object_or_404(Sede, pk=sede['id_sede'])
                c_sede = sede.get('cuposAsignados') if 'cuposAsignados' in sede else sede.get('cupos_asignados', sede.get('cupos', 0))
                cupos_sede_int = int(c_sede or 0)
                dist_sede = DistribucionSede.objects.create(
                    id_contrato=contrato,
                    id_sede=sede_obj,
                    cupos_asignados=cupos_sede_int,
                )

                if hasattr(sede_obj, 'cupos') and getattr(sede_obj, 'cupos', None) != cupos_sede_int:
                    sede_obj.cupos = cupos_sede_int
                    sede_obj.save(update_fields=['cupos'])

                for grado in sede.get('grados', []):
                    grado_obj = get_object_or_404(Grados, pk=grado['id_grado'])
                    c_grado = grado.get('cuposAsignados') if 'cuposAsignados' in grado else grado.get('cupos_asignados', grado.get('cupos', 0))
                    cupos_grado_int = int(c_grado or 0)
                    DistribucionGrado.objects.update_or_create(
                        id_distribucion_sede=dist_sede,
                        id_grado=grado_obj,
                        defaults={'cupos_asignados': cupos_grado_int},
                    )

                # Sincronizar SedeJornada con las jornadas reales seleccionadas para la sede
                jornadas_a_sincronizar = []
                es_manana = bool(sede.get('jornada_manana'))
                es_tarde = bool(sede.get('jornada_tarde'))
                jornadas_list = sede.get('jornadas') or []
                if isinstance(jornadas_list, list):
                    if any('mañan' in str(j).lower() for j in jornadas_list):
                        es_manana = True
                    if any('tard' in str(j).lower() for j in jornadas_list):
                        es_tarde = True

                if es_manana and jornada_manana_obj:
                    jornadas_a_sincronizar.append(jornada_manana_obj)
                if es_tarde and jornada_tarde_obj:
                    jornadas_a_sincronizar.append(jornada_tarde_obj)
                if not jornadas_a_sincronizar and jornada_default:
                    jornadas_a_sincronizar.append(jornada_default)

                for j_obj in jornadas_a_sincronizar:
                    sj, _ = SedeJornada.objects.update_or_create(
                        id_sede=sede_obj,
                        id_jornada=j_obj,
                        defaults={'cupos': cupos_sede_int},
                    )

                    for grado in sede.get('grados', []):
                        grado_obj = get_object_or_404(Grados, pk=grado['id_grado'])
                        c_grado = grado.get('cuposAsignados') if 'cuposAsignados' in grado else grado.get('cupos_asignados', grado.get('cupos', 0))
                        cupos_grado_int = int(c_grado or 0)
                        SedeJornadaGrado.objects.update_or_create(
                            id_sede_jornada=sj,
                            id_grado=grado_obj,
                            defaults={'cupos': cupos_grado_int, 'estado': 'ACTIVO'},
                        )

        # 5. Devolver la distribución actualizada
        return self._get_distribucion(contrato)
