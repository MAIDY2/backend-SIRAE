from rest_framework import viewsets
from rest_framework.response import Response

from ..models import Institucion, SupervisorInstitucion
from .serializers import InstitucionSerializer, SupervisorInstitucionSerializer
from apps_sirae.usuarios.alcance import obtener_instituciones_autorizadas
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class InstitucionViewSet(viewsets.ModelViewSet):
    queryset = Institucion.objects.all()
    serializer_class = InstitucionSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        qs = Institucion.objects.all().prefetch_related(
            'sedes',
            'supervisores_asignados__id_supervisor'
        )
        return obtener_instituciones_autorizadas(self.request.user, qs)

    def list(self, request, *args, **kwargs):
        # Forzamos una respuesta de lista plana para que Angular no sufra por paginación
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SupervisorInstitucionViewSet(viewsets.ModelViewSet):
    queryset = SupervisorInstitucion.objects.select_related(
        'id_supervisor',
        'id_institucion'
    ).all()

    serializer_class = SupervisorInstitucionSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()

        supervisor_id = self.request.query_params.get('id_supervisor')

        if supervisor_id:
            queryset = queryset.filter(
                id_supervisor_id=supervisor_id
            )

        institucion_id = self.request.query_params.get('id_institucion')

        if institucion_id:
            queryset = queryset.filter(
                id_institucion_id=institucion_id
            )

        return queryset
