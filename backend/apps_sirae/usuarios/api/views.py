from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth import authenticate

from rest_framework_simplejwt.tokens import RefreshToken
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

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

    # Define los campos que Swagger mostrará en la interfaz
    @swagger_auto_schema(
        request_body=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            required=['correo', 'password'],
            properties={
                'correo': openapi.Schema(type=openapi.TYPE_STRING, description='Correo electrónico del usuario', example='admin@sirae.com'),
                'password': openapi.Schema(type=openapi.TYPE_STRING, description='Contraseña', example='123456'),
            },
        ),
        responses={
            200: openapi.Response('Login exitoso con tokens JWT'),
            401: 'Credenciales inválidas',
            400: 'Petición incorrecta'
        }
    )
    def post(self, request):
        correo = request.data.get('correo')
        password = request.data.get('password')

        if not correo or not password:
            return Response(
                {'error': 'Debe proporcionar correo y contraseña'},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = authenticate(
            request=request,
            username=correo,
            password=password
        )

        if user is not None:
            refresh = RefreshToken.for_user(user)

            # Inyectar id_usuario en las claims del JWT
            refresh['user_id'] = user.id_usuario
            refresh['correo'] = user.correo

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
            {'error': 'Credenciales inválidas'},
            status=status.HTTP_401_UNAUTHORIZED
        )