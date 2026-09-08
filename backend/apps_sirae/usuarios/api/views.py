from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from ..models import Usuario, Rol
from .serializers import UsuarioSerializer, RolSerializer
from ..permissions import IsAdminRole, IsAdminOrReadOnly


class UsuarioViewSet(viewsets.ModelViewSet):
    """
    CRUD completo de Usuarios en SIRAE.
    Exclusivo para el rol Administrador.
    Permite filtrar por id_rol, estado y buscar por nombre, correo o documento.
    """
    queryset = Usuario.objects.select_related('id_rol').all().order_by('id_usuario')
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def get_queryset(self):
        queryset = super().get_queryset()
        rol_id = self.request.query_params.get('id_rol')
        estado = self.request.query_params.get('estado')
        search = self.request.query_params.get('search')

        if rol_id:
            queryset = queryset.filter(id_rol_id=rol_id)
        if estado:
            queryset = queryset.filter(estado__iexact=estado)
        if search:
            search = search.strip()
            queryset = queryset.filter(
                Q(nombre_completo__icontains=search) |
                Q(email__icontains=search) |
                Q(documento_identidad__icontains=search)
            )
        return queryset

    @action(detail=True, methods=['post'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        """
        Alterna o asigna el estado de un usuario (Activo / Inactivo).
        """
        usuario = self.get_object()
        nuevo_estado = request.data.get('estado')

        if not nuevo_estado:
            nuevo_estado = 'Inactivo' if usuario.is_active else 'Activo'

        usuario.estado = nuevo_estado
        usuario.save()

        return Response({
            "status": "success",
            "mensaje": f"El estado del usuario {usuario.nombre_completo} ha sido cambiado a '{nuevo_estado}'.",
            "id_usuario": usuario.id_usuario,
            "estado": usuario.estado
        }, status=status.HTTP_200_OK)


class RolViewSet(viewsets.ModelViewSet):
    """
    Gestión y consulta de Roles en SIRAE.
    Lectura permitida para cualquier usuario autenticado;
    modificación reservada exclusivamente al Administrador.
    """
    queryset = Rol.objects.all().order_by('id_rol')
    serializer_class = RolSerializer
    permission_classes = [IsAuthenticated, IsAdminOrReadOnly]