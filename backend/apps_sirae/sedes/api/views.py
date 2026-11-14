
from django.db.models import Sum
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from ..models import Sede
from .serializers import SedeSerializer
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.contratos_seccion_menu.models import ContratoSeccionMenu
from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
from apps_sirae.sede_jornada.services import guardar_configuracion_sede
from apps_sirae.usuarios.alcance import obtener_sedes_autorizadas
from apps_sirae.usuarios.permissions import IsAdminRole, IsSuperAdminOrReadOnly


class SedeViewSet(viewsets.ModelViewSet):
    queryset = Sede.objects.all()
    serializer_class = SedeSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = obtener_sedes_autorizadas(self.request.user, super().get_queryset())

        # Filtro opcional por institución.
        institucion_id = self.request.query_params.get('id_institucion')

        if institucion_id:
            queryset = queryset.filter(
                id_institucion_id=institucion_id
            )

        return queryset

    @action(
        detail=True,
        methods=['get', 'post'],
        url_path='configuracion',
        permission_classes=[IsAdminRole],
    )
    def configuracion(self, request, pk=None):
        sede = self.get_object()

        # ── POST: guardar jornadas + cupos + grados ──────────────────────────
        if request.method == 'POST':
            jornadas_payload = request.data.get('jornadas', [])
            try:
                resultado = guardar_configuracion_sede(
                    sede=sede,
                    usuario=request.user,
                    jornadas=jornadas_payload,
                )
            except ValidationError as exc:
                return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
            except Exception as exc:
                return Response(
                    {'detail': str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                {
                    'mensaje': 'Configuración guardada correctamente.',
                    'jornadas': resultado,
                },
                status=status.HTTP_200_OK,
            )

        # ── GET: consultar configuración actual ──────────────────────────────
        contratos = Contrato.objects.filter(id_sede_id=sede.id_sede)
        cupos_totales = contratos.aggregate(total=Sum('cupos'))['total'] or 0
        cupos_por_jornada = {
            item['id_jornada_id']: item['total'] or 0
            for item in contratos.values('id_jornada_id').annotate(total=Sum('cupos'))
            if item['id_jornada_id'] is not None
        }

        # Identificar jornadas autorizadas para esta sede mediante sus contratos
        jornadas_autorizadas_ids = set(cupos_por_jornada.keys())

        # Secciones de menú por jornada
        secciones = ContratoSeccionMenu.objects.filter(
            id_contrato__in=contratos
        ).select_related(
            'id_contrato__id_jornada',
            'id_seccion',
            'id_seccion__id_jornada',
        ).order_by('id_seccion__nombre_seccion')

        for conf in secciones:
            j_id = (
                conf.id_contrato.id_jornada_id
                or conf.id_seccion.id_jornada_id
            )
            if j_id:
                jornadas_autorizadas_ids.add(j_id)

        # Jornadas configuradas con sus cupos asignados por el admin
        sede_jornadas = list(
            SedeJornada.objects.filter(id_sede=sede)
            .select_related('id_jornada')
            .prefetch_related('grados_atendidos__id_grado')
            .order_by('id_jornada__nombre_jornada')
        )

        jornada_por_id = {}
        for sj in sede_jornadas:
            # Si existen contratos configurados, no mostrar jornadas ajenas sin cupos ni registros
            if jornadas_autorizadas_ids and sj.id_jornada_id not in jornadas_autorizadas_ids:
                if sj.cupos == 0 and not sj.grados_atendidos.filter(estado='ACTIVO', cupos__gt=0).exists():
                    continue

            # Grados activos con sus cupos guardados en BD
            grados_guardados = [
                {
                    'id_grado': g.id_grado_id,
                    'nombre_grado': g.id_grado.nombre_grado,
                    'cupos': g.cupos,
                }
                for g in sorted(
                    (item for item in sj.grados_atendidos.all() if item.estado == 'ACTIVO'),
                    key=lambda item: (item.id_grado.nombre_grado or '').lower(),
                )
            ]

            cupos_jornada = sj.cupos if sj.cupos > 0 else cupos_por_jornada.get(sj.id_jornada_id, 0)
            if cupos_jornada == 0 and len(jornadas_autorizadas_ids) == 1 and cupos_totales > 0:
                cupos_jornada = cupos_totales

            jornada_por_id[sj.id_jornada_id] = {
                'id_jornada': sj.id_jornada_id,
                'nombre_jornada': sj.id_jornada.nombre_jornada or 'Jornada sin nombre',
                'cupos': cupos_jornada,
                'habilitada': True,
                'secciones': [],
                'grados': grados_guardados,
            }

        # Si hay jornadas autorizadas en contratos que no tenían SedeJornada, agregarlas
        if jornadas_autorizadas_ids:
            from apps_sirae.jornadas.models import Jornada
            for j_id in sorted(jornadas_autorizadas_ids):
                if j_id not in jornada_por_id:
                    j_obj = Jornada.objects.filter(pk=j_id).first()
                    if j_obj:
                        cupos_j = cupos_por_jornada.get(j_id, 0)
                        if cupos_j == 0 and len(jornadas_autorizadas_ids) == 1:
                            cupos_j = cupos_totales
                        jornada_por_id[j_id] = {
                            'id_jornada': j_id,
                            'nombre_jornada': j_obj.nombre_jornada or 'Jornada sin nombre',
                            'cupos': cupos_j,
                            'habilitada': True,
                            'secciones': [],
                            'grados': [],
                        }

        for conf in secciones:
            jornada_id = (
                conf.id_contrato.id_jornada_id
                or conf.id_seccion.id_jornada_id
            )
            jornada = jornada_por_id.get(jornada_id)
            if not jornada and len(jornada_por_id) == 1:
                jornada = next(iter(jornada_por_id.values()))
            if not jornada:
                continue
            jornada['secciones'].append({
                'id_seccion': conf.id_seccion_id,
                'nombre_seccion': (
                    conf.id_seccion.nombre_seccion
                    or f"Sección {conf.id_seccion_id}"
                ),
                'estado': conf.estado,
            })

        # Asegurar catálogo de grados activos disponible para cada jornada
        from apps_sirae.grados.models import Grados
        todos_grados = list(
            Grados.objects.filter(estado='ACTIVO').order_by('nombre_grado')
        )
        for jornada in jornada_por_id.values():
            existentes = {g['id_grado'] for g in jornada['grados']}
            for g in todos_grados:
                if g.id_grado not in existentes:
                    jornada['grados'].append({
                        'id_grado': g.id_grado,
                        'nombre_grado': g.nombre_grado,
                        'cupos': 0,
                    })
            jornada['grados'].sort(key=lambda item: (item['nombre_grado'] or '').lower())

        # Historial de cambios
        from apps_sirae.sede_jornada.models import HistorialConfiguracionSede
        historial_qs = (
            HistorialConfiguracionSede.objects
            .filter(id_sede=sede)
            .select_related('usuario')
            .order_by('-fecha_hora')[:20]
        )
        historial_formateado = [
            {
                'id': h.id_historial,
                'fecha_hora': h.fecha_hora,
                'usuario': h.usuario.nombre_completo if h.usuario else 'Sistema',
                'descripcion': 'Se modificó la configuración de jornadas y cupos de la sede.',
            }
            for h in historial_qs
        ]

        return Response({
            'sede': SedeSerializer(sede).data,
            'cupos_totales': cupos_totales,
            'jornadas': list(jornada_por_id.values()),
            'historial': historial_formateado,
        })
