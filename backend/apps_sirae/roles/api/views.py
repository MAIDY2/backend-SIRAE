from django.db.models import Q
from rest_framework import viewsets

from apps_sirae.roles.models import Rol
from apps_sirae.roles.api.serializers import RolSerializer


class RolViewSet(viewsets.ModelViewSet):
    queryset = Rol.objects.all().order_by('id_rol')
    serializer_class = RolSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        solo_asignables = str(
            self.request.query_params.get('asignables', '')
        ).strip().lower() in {'1', 'true', 'yes', 'si'}

        if not solo_asignables:
            return qs

        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return qs.none()

        if user.es_super_administrador():
            return qs.filter(
                (Q(nombre__icontains='admin') & ~Q(nombre__icontains='super'))
                | Q(nombre__icontains='supervisor')
                | Q(nombre__icontains='coordinador')
            )

        if user.es_administrador():
            return qs.filter(
                Q(nombre__icontains='manipuladora')
                | Q(nombre__icontains='jefa')
                | Q(nombre__icontains='cocina')
            )

        return qs.none()
