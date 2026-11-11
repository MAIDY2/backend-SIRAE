
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
        }

        # Jornadas configuradas con sus cupos asignados por el admin
        sede_jornadas = list(
            SedeJornada.objects.filter(id_sede=sede)
            .select_related('id_jornada')
            .prefetch_related('grados__id_grado')
            .order_by('id_jornada__nombre_jornada')
        )

        jornada_por_id = {}
        for sj in sede_jornadas:
            # Grados con sus cupos guardados en BD
            grados_guardados = [
                {
                    'id_grado': g.id_grado_id,
                    'nombre_grado': g.id_grado.nombre_grado,
                    'cupos': g.cupos,
                }
                for g in sj.grados.all().select_related('id_grado').order_by('id_grado__nombre_grado')
            ]
            jornada_por_id[sj.id_jornada_id] = {
                'id_jornada': sj.id_jornada_id,
                'nombre_jornada': sj.id_jornada.nombre_jornada or 'Jornada sin nombre',
                'cupos': sj.cupos,
                'habilitada': True,
                'secciones': [],
                'grados': grados_guardados,
            }

        # Secciones de menú por jornada
        secciones = ContratoSeccionMenu.objects.filter(
            id_contrato__in=contratos
        ).select_related(
            'id_contrato__id_jornada',
            'id_seccion',
            'id_seccion__id_jornada',
        ).order_by('id_seccion__nombre_seccion')

        for conf in secciones:
            jornada_id = (
                conf.id_contrato.id_jornada_id
                or conf.id_seccion.id_jornada_id
            )
            jornada = jornada_por_id.get(jornada_id)
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
