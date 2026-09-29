from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth.forms import PasswordResetForm

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from apps_sirae.usuarios.models import Usuario
from apps_sirae.usuarios.api.serializers import UsuarioSerializer, CustomTokenObtainPairSerializer


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
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer


class RecuperarPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('correo')
        if not email:
            return Response(
                {"detail": "El correo electrónico es obligatorio."}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verificación adaptada al campo 'correo' de tu modelo
        usuario_existe = Usuario.objects.filter(correo=email).exists()
        
        if usuario_existe:
            form = PasswordResetForm({'email': email})
            if form.is_valid():
                form.save(
                    request=request,
                    use_https=request.is_secure(),
                    email_template_name='registration/password_reset_email.html',
                )
        
        return Response(
            {"detail": "Si el correo está registrado, se han enviado las instrucciones."}, 
            status=status.HTTP_200_OK
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def google_login_view(request):
    token_google = request.data.get('token')
    
    if not token_google:
        return Response({"detail": "Token de Google no proporcionado."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Reemplaza 'TU_GOOGLE_CLIENT_ID' con tu Client ID real de Google Cloud Console cuando lo tengas
        CLIENT_ID = "TU_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
        
        # Verificamos el token con los servidores de Google
        idinfo = id_token.verify_oauth2_token(token_google, google_requests.Request(), CLIENT_ID)

        email = idinfo['email']
        nombre = idinfo.get('given_name', '')
        apellido = idinfo.get('family_name', '')

        # Buscamos o creamos el usuario en tu base de datos local usando tu campo 'correo'
        usuario, creado = Usuario.objects.get_or_create(
            correo=email,
            defaults={
                'nombre': nombre,
                'apellido': apellido,
                'password': Usuario.objects.make_random_password() 
            }
        )

        # Generamos los tokens JWT de SimpleJWT para tu sistema
        refresh = RefreshToken.for_user(usuario)

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'usuario': UsuarioSerializer(usuario).data
        }, status=status.HTTP_200_OK)

    except ValueError:
        return Response({"detail": "Token de Google inválido."}, status=status.HTTP_400_BAD_REQUEST)