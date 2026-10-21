from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from rest_framework_simplejwt.views import TokenObtainPairView

from apps_sirae.usuarios.models import Usuario
from apps_sirae.usuarios.api.serializers import UsuarioSerializer, CustomTokenObtainPairSerializer
from apps_sirae.usuarios.api.password_reset import (
    ConfirmarCodigoRecuperacionPasswordView,
    SolicitarCodigoRecuperacionPasswordView,
)


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.select_related('rol', 'id_institucion', 'id_sede').all()
    serializer_class = UsuarioSerializer

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Usuario.objects.none()

        # Super Administrador ve todos los usuarios del sistema
        if user.es_super_administrador() or user.is_superuser:
            return Usuario.objects.select_related('rol', 'id_institucion', 'id_sede').all()

        # Administrador regular solo ve los usuarios de su propia institución
        if user.es_administrador():
            if user.id_institucion_id:
                return Usuario.objects.select_related('rol', 'id_institucion', 'id_sede').filter(
                    id_institucion=user.id_institucion_id
                )
            return Usuario.objects.select_related('rol', 'id_institucion', 'id_sede').filter(
                id_usuario=user.id_usuario
            )

        # Los demás roles solo pueden ver su propio perfil
        return Usuario.objects.select_related('rol', 'id_institucion', 'id_sede').filter(
            id_usuario=user.id_usuario
        )

    def perform_destroy(self, instance):
        if instance.es_super_administrador():
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied('El Super Administrador no puede ser eliminado del sistema.')
        super().perform_destroy(instance)


class RegistroView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UsuarioSerializer(data=request.data)
        if serializer.is_valid():
            usuario = serializer.save()
            return Response(
                {
                    'mensaje': 'Usuario registrado exitosamente',
                    'data': UsuarioSerializer(usuario).data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


RecuperarPasswordView = SolicitarCodigoRecuperacionPasswordView
