
from django.db.models import Sum
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from ..models import Sede
from .serializers import SedeSerializer
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.contratos_seccion_menu.models import ContratoSeccionMenu
from apps_sirae.sede_jornada.models import SedeJornada
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
        methods=['get'],
        url_path='configuracion',
        permission_classes=[IsAdminRole],
    )
    def configuracion(self, request, pk=None):
        sede = self.get_object()
        contratos = Contrato.objects.filter(id_sede_id=sede.id_sede)
        cupos_totales = contratos.aggregate(total=Sum('cupos'))['total'] or 0
        cupos_por_jornada = {
            item['id_jornada_id']: item['total'] or 0
            for item in contratos.values('id_jornada_id').annotate(total=Sum('cupos'))
        }

        jornadas = list(
            SedeJornada.objects.filter(id_sede=sede)
            .select_related('id_jornada')
            .order_by('id_jornada__nombre_jornada')
        )
        jornada_por_id = {
            jornada.id_jornada_id: {
                'id_jornada': jornada.id_jornada_id,
                'nombre_jornada': jornada.id_jornada.nombre_jornada or 'Jornada sin nombre',
                'cupos': cupos_por_jornada.get(jornada.id_jornada_id, 0),
                'secciones': [],
            }
            for jornada in jornadas
        }

        secciones = ContratoSeccionMenu.objects.filter(
            id_contrato__in=contratos
        ).select_related(
            'id_contrato__id_jornada',
            'id_seccion',
            'id_seccion__id_jornada',
        ).order_by('id_seccion__nombre_seccion')

        for configuracion in secciones:
            jornada_id = (
                configuracion.id_contrato.id_jornada_id
                or configuracion.id_seccion.id_jornada_id
            )
            jornada = jornada_por_id.get(jornada_id)
            if not jornada:
                continue
            jornada['secciones'].append({
                'id_seccion': configuracion.id_seccion_id,
                'nombre_seccion': (
                    configuracion.id_seccion.nombre_seccion
                    or f"Sección {configuracion.id_seccion_id}"
                ),
                'estado': configuracion.estado,
            })

        return Response({
            'sede': SedeSerializer(sede).data,
            'cupos_totales': cupos_totales,
            'jornadas': list(jornada_por_id.values()),
        })
