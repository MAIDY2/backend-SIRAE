
from django.db.models import Q
from rest_framework import viewsets

from ..models import Sede
from .serializers import SedeSerializer
from apps_sirae.usuarios.permissions import IsSuperAdminOrReadOnly


class SedeViewSet(viewsets.ModelViewSet):
    queryset = Sede.objects.all()
    serializer_class = SedeSerializer
    permission_classes = [IsSuperAdminOrReadOnly]

    def get_queryset(self):
        queryset = super().get_queryset()
        usuario = self.request.user

        if usuario.is_authenticated:

            # El Super Administrador puede ver todas las sedes.
            if usuario.es_super_administrador():
                pass

            # El Supervisor solamente ve sus sedes asignadas.
            elif usuario.es_supervisor():
                filtro = Q(
                    id_institucion__supervisores_asignados__id_supervisor=usuario
                )

                # Institución asociada directamente al supervisor.
                if usuario.id_institucion_id:
                    filtro |= Q(
                        id_institucion_id=usuario.id_institucion_id
                    )

                # Contratos asociados a una institución.
                filtro |= Q(
                    id_institucion__contratos__id_usuario_supervisor=usuario
                )

                # Contratos asociados directamente a una sede.
                filtro |= Q(
                    contratos__id_usuario_supervisor=usuario
                )

                queryset = queryset.filter(filtro).distinct()

            # Administrador regular: solamente su institución.
            elif usuario.es_administrador() and usuario.id_institucion_id:
                queryset = queryset.filter(
                    id_institucion_id=usuario.id_institucion_id
                )

        # Filtro opcional por institución.
        institucion_id = self.request.query_params.get('id_institucion')

        if institucion_id:
            queryset = queryset.filter(
                id_institucion_id=institucion_id
            )

        return queryset
