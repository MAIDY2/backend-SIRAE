from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth.forms import PasswordResetForm
from django.conf import settings
from django.db import IntegrityError

from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.tokens import RefreshToken
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from google.auth.exceptions import GoogleAuthError

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

    if not isinstance(token_google, str) or not token_google.strip():
        return Response({"detail": "Token de Google no proporcionado."}, status=status.HTTP_400_BAD_REQUEST)

    client_id = settings.GOOGLE_OAUTH2_CLIENT_ID
    if not client_id:
        return Response(
            {"detail": "La autenticación con Google no está configurada."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    try:
        idinfo = id_token.verify_oauth2_token(
            token_google,
            google_requests.Request(),
            client_id
        )
    except ValueError:
        return Response({"detail": "Token de Google inválido."}, status=status.HTTP_401_UNAUTHORIZED)
    except GoogleAuthError:
        return Response(
            {"detail": "No se pudo verificar el token con Google."},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    email = idinfo.get('email')
    if not isinstance(email, str) or not email.strip() or idinfo.get('email_verified') is not True:
        return Response(
            {"detail": "El token no contiene un correo verificado."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    email = email.strip().lower()
    try:
        usuario = Usuario.objects.get(correo__iexact=email)
    except Usuario.DoesNotExist:
        tipo_documento = request.data.get('tipo_documento')
        numero_documento = request.data.get('numero_documento')
        if not isinstance(tipo_documento, str) or not tipo_documento.strip():
            return Response(
                {"tipo_documento": "Este campo es obligatorio para crear la cuenta."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not isinstance(numero_documento, str) or not numero_documento.strip():
            return Response(
                {"numero_documento": "Este campo es obligatorio para crear la cuenta."},
                status=status.HTTP_400_BAD_REQUEST
            )

        tipo_documento = tipo_documento.strip()
        numero_documento = numero_documento.strip()
        if len(tipo_documento) > 20 or len(numero_documento) > 20:
            return Response(
                {"detail": "El tipo y número de documento no pueden superar 20 caracteres."},
                status=status.HTTP_400_BAD_REQUEST
            )
        if Usuario.objects.filter(numero_documento=numero_documento).exists():
            return Response(
                {"numero_documento": "Este número de documento ya está registrado."},
                status=status.HTTP_409_CONFLICT
            )

        try:
            usuario = Usuario.objects.create_user(
                correo=email,
                nombre=idinfo.get('given_name') or '',
                apellido=idinfo.get('family_name') or '',
                tipo_documento=tipo_documento,
                numero_documento=numero_documento
            )
        except IntegrityError:
            usuario = Usuario.objects.filter(correo__iexact=email).first()
            if usuario is None:
                return Response(
                    {"detail": "El número de documento ya está registrado."},
                    status=status.HTTP_409_CONFLICT
                )

    if not usuario.is_active:
        return Response({"detail": "La cuenta del usuario está inactiva."}, status=status.HTTP_403_FORBIDDEN)

    refresh = RefreshToken.for_user(usuario)
    return Response({
        'access': str(refresh.access_token),
        'refresh': str(refresh),
        'usuario': UsuarioSerializer(usuario).data
    }, status=status.HTTP_200_OK)