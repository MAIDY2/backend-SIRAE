# -*- coding: utf-8 -*-
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from apps_sirae.roles.models import Rol
from apps_sirae.usuarios.permissions import IsAdminOrReadOnly
from .serializers import RolSerializer


class RolViewSet(viewsets.ModelViewSet):
    """
    CRUD de Roles.
    - GET    /api/roles/        → lista todos los roles (autenticado)
    - GET    /api/roles/{id}/   → detalle de un rol (autenticado)
    - POST   /api/roles/        → crear rol (solo Administrador)
    - PUT/PATCH /api/roles/{id}/→ editar rol (solo Administrador)
    - DELETE /api/roles/{id}/   → eliminar rol (solo Administrador)
    """
    queryset           = Rol.objects.all()
    serializer_class   = RolSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]
