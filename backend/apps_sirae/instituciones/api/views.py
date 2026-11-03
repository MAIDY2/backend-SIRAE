from rest_framework import viewsets, permissions
from django.db.models import Q

from ..models import Institucion, SupervisorInstitucion
from .serializers import InstitucionSerializer, SupervisorInstitucionSerializer
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class InstitucionViewSet(viewsets.ModelViewSet):
    queryset = Institucion.objects.all()
    serializer_class = InstitucionSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        user = self.request.user
        qs = Institucion.objects.all().prefetch_related('sedes', 'supervisores_asignados__id_supervisor')

        if not user or not user.is_authenticated:
            return qs

        # Super Administrador ve todas las instituciones
        if user.es_super_administrador() or user.is_superuser:
            return qs

        # Supervisor ve solo las instituciones que tiene asignadas
        if user.es_supervisor():
            asignadas_ids = set(user.instituciones_asignadas.values_list('id_institucion_id', flat=True))
            from apps_sirae.contratos_pae.models import Contrato
            contratos_ids = set(
                Contrato.objects.filter(id_usuario_supervisor=user).values_list('id_institucion_id', flat=True)
            )
            ids_totales = asignadas_ids.union({cid for cid in contratos_ids if cid})
            if ids_totales:
                return qs.filter(id_institucion__in=ids_totales)
            # Si aún no tiene asignadas, retorna vacío para que no vea colegios de otros supervisores
            return Institucion.objects.none()

        # Administrador regular ve su institución asignada
        if user.es_administrador() and user.id_institucion_id:
            return qs.filter(id_institucion=user.id_institucion_id)

        return qs


class SupervisorInstitucionViewSet(viewsets.ModelViewSet):
    queryset = SupervisorInstitucion.objects.select_related('id_supervisor', 'id_institucion').all()
    serializer_class = SupervisorInstitucionSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        supervisor_id = self.request.query_params.get('id_supervisor')
        if supervisor_id:
            queryset = queryset.filter(id_supervisor_id=supervisor_id)
        institucion_id = self.request.query_params.get('id_institucion')
        if institucion_id:
            queryset = queryset.filter(id_institucion_id=institucion_id)
        return queryset