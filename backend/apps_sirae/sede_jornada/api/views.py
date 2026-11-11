from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps_sirae.usuarios.alcance import obtener_sede_jornadas_autorizadas
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly
from ..models import SedeJornada
from .serializers import SedeJornadaSerializer


class SedeJornadaViewSet(viewsets.ModelViewSet):
    queryset = SedeJornada.objects.select_related(
        'id_sede',
        'id_sede__id_institucion',
        'id_jornada',
    ).prefetch_related('grados__id_grado__id_grupo_gramaje').all()
    serializer_class = SedeJornadaSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = obtener_sede_jornadas_autorizadas(
            self.request.user,
            super().get_queryset(),
        )
        institucion_id = self.request.query_params.get('id_institucion')
        sede_id = self.request.query_params.get('id_sede')
        jornada_id = self.request.query_params.get('id_jornada')

        if institucion_id:
            queryset = queryset.filter(id_sede__id_institucion_id=institucion_id)
        if sede_id:
            queryset = queryset.filter(id_sede_id=sede_id)
        if jornada_id:
            queryset = queryset.filter(id_jornada_id=jornada_id)

        return queryset

    @action(detail=True, methods=['post', 'put'], url_path='asignar-grados')
    def asignar_grados(self, request, pk=None):
        sede_jornada = self.get_object()
        serializer = self.get_serializer(
            sede_jornada,
            data={'grados_ids': request.data.get('grados_ids', [])},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
