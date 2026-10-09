from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.contrib.auth.forms import PasswordResetForm

from rest_framework_simplejwt.views import TokenObtainPairView

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
