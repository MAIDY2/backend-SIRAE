import pickle
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UsuarioBiometria
from .utils import compare_embeddings, image_to_embedding

User = get_user_model()


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def register_face(request):
    """
    Registra o actualiza la biometría facial de un usuario autenticado (desde Mi Perfil).
    Por seguridad, solo un usuario con sesión iniciada puede vincular o renovar su rostro.
    """
    usuario = request.user
    
    # Si un superadministrador desea registrar el rostro de otro usuario:
    correo_objetivo = request.data.get('correo')
    if correo_objetivo and (usuario.is_superuser or getattr(getattr(usuario, 'rol', None), 'nombre', '') == 'Superadministrador'):
        target = User.objects.filter(correo__iexact=str(correo_objetivo).strip()).first()
        if target:
            usuario = target

    image = request.data.get('image')
    if not image:
        return Response(
            {"detail": "Debe proporcionar la captura de imagen."},
            status=status.HTTP_400_BAD_REQUEST
        )

    embedding = image_to_embedding(image)
    if embedding is None:
        return Response(
            {"detail": "No se detectó un rostro claro en la imagen. Enfoca bien la cámara e inténtalo de nuevo."},
            status=status.HTTP_400_BAD_REQUEST
        )

    emb_serialized = pickle.dumps(embedding)

    UsuarioBiometria.objects.update_or_create(
        usuario=usuario,
        defaults={
            "embedding": emb_serialized,
            "activo": True
        }
    )

    rol_obj = getattr(usuario, 'rol', None)
    rol_nombre = getattr(rol_obj, 'nombre', str(rol_obj)) if rol_obj else ''

    return Response({
        "msg": f"Rostro registrado exitosamente para {usuario.nombre} ({rol_nombre})",
        "usuario": usuario.correo
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def eliminar_biometria(request):
    """
    Permite al usuario autenticado desvincular su biometría facial.
    """
    UsuarioBiometria.objects.filter(usuario=request.user).delete()
    return Response({"detail": "Biometría eliminada exitosamente."}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def estado_biometria(request):
    """
    Consulta si el usuario autenticado tiene su biometría facial registrada.
    """
    tiene_biometria = UsuarioBiometria.objects.filter(usuario=request.user, activo=True).exists()
    return Response({
        "tiene_biometria": tiene_biometria,
        "correo": request.user.correo
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_face(request):
    """
    Equivalente a @app.post('/verify-face') de tu instructora.
    Recibe: image (base64).
    Compara con los rostros registrados. Si hay coincidencia, inicia sesión emitiendo el JWT de SIRAE.
    """
    image = request.data.get('image')
    if not image:
        return Response(
            {"detail": "No se recibió ninguna imagen para verificar."},
            status=status.HTTP_400_BAD_REQUEST
        )

    embedding_actual = image_to_embedding(image)
    if embedding_actual is None:
        return Response(
            {"detail": "No se detectó ningún rostro en la cámara."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Recorremos los usuarios con biometría registrada activa
    biometrias = UsuarioBiometria.objects.filter(activo=True).select_related('usuario', 'usuario__rol')
    for bio in biometrias:
        try:
            db_embedding = pickle.loads(bio.embedding)
            if compare_embeddings(db_embedding, embedding_actual):
                usuario = bio.usuario
                if not usuario.is_active:
                    return Response(
                        {"detail": "Esta cuenta se encuentra inactiva."},
                        status=status.HTTP_403_FORBIDDEN
                    )

                # Generar tokens de sesión JWT
                refresh = RefreshToken.for_user(usuario)
                rol_obj = getattr(usuario, 'rol', None)
                rol_str = getattr(rol_obj, 'nombre', '') if rol_obj else ''

                return Response({
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                    "usuario": {
                        "id_usuario": usuario.pk,
                        "correo": usuario.correo,
                        "nombre": usuario.nombre,
                        "apellido": getattr(usuario, 'apellido', ''),
                        "rol": rol_str,
                    },
                    "msg": f"Bienvenido(a) {usuario.nombre}"
                }, status=status.HTTP_200_OK)
        except Exception:
            continue

    return Response(
        {"detail": "Rostro no reconocido en el sistema. Asegúrate de haberlo registrado previamente."},
        status=status.HTTP_401_UNAUTHORIZED
    )
