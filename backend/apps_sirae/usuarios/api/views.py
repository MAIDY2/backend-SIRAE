from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps_sirae.usuarios.models import Usuario
from apps_sirae.usuarios.permissions import IsAdminRole, IsAdminOrReadOnly
from .serializers import (
    UsuarioSerializer,
    UsuarioCreateSerializer,
    UsuarioUpdateSerializer,
    CambioPasswordSerializer,
)


class UsuarioViewSet(viewsets.ModelViewSet):
    """
    CRUD de Usuarios.
    - GET    /api/usuarios/            → lista (solo Admin)
    - GET    /api/usuarios/{id}/       → detalle (solo Admin)
    - POST   /api/usuarios/            → crear (solo Admin)
    - PUT/PATCH /api/usuarios/{id}/    → editar (solo Admin)
    - DELETE /api/usuarios/{id}/       → eliminar (solo Admin)
    - POST   /api/usuarios/yo/cambiar-password/ → cambiar propia contraseña
    - GET    /api/usuarios/yo/         → ver mi propio perfil
    """
    queryset           = Usuario.objects.select_related('rol').all()
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]

    def get_serializer_class(self):
        if self.action == 'create':
            return UsuarioCreateSerializer
        if self.action in ('update', 'partial_update'):
            return UsuarioUpdateSerializer
        return UsuarioSerializer

    # GET /api/usuarios/yo/
    @action(detail=False, methods=['get'], url_path='yo', permission_classes=[IsAuthenticated])
    def mi_perfil(self, request):
        serializer = UsuarioSerializer(request.user)
        return Response(serializer.data)

    # POST /api/usuarios/yo/cambiar-password/
    @action(detail=False, methods=['post'], url_path='yo/cambiar-password', permission_classes=[IsAuthenticated])
    def cambiar_password(self, request):
        serializer = CambioPasswordSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['password_nuevo'])
        request.user.save()
        return Response({'detail': 'Contraseña actualizada correctamente.'}, status=status.HTTP_200_OK)
