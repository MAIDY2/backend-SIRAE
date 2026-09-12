from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate

from rest_framework_simplejwt.tokens import RefreshToken

from apps_sirae.usuarios.models import Usuario
from apps_sirae.usuarios.api.serializers import UsuarioSerializer


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.all()
    serializer_class = UsuarioSerializer


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

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        correo = request.data.get('correo')
        password = request.data.get('password')

        user = authenticate(
            username=correo,
            password=password
        )

        if user is not None:

            refresh = RefreshToken.for_user(user)

            return Response(
                {
                    'token': str(refresh.access_token),
                    'refresh': str(refresh),
                    'usuario': {
                        'id_usuario': user.id_usuario,
                        'nombre': user.nombre,
                        'apellido': user.apellido,
                        'correo': user.correo,
                        'rol': user.rol.nombre if user.rol else None
                    }
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                'error': 'Credenciales inválidas'
            },
            status=status.HTTP_401_UNAUTHORIZED
        )