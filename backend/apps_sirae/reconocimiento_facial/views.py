import pickle
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from .models import UsuarioBiometria
from .utils import compare_embeddings, image_to_embedding, calcular_distancia_embedding

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

    plataforma = str(request.data.get('plataforma') or request.query_params.get('plataforma') or '').strip().lower()

    # Recorremos todas las biometrías activas y encontramos el mejor match (menor distancia global)
    biometrias = UsuarioBiometria.objects.filter(activo=True).select_related('usuario', 'usuario__rol')
    mejor_usuario = None
    mejor_distancia = 999.0
    UMBRAL_MAXIMO = 0.60

    for bio in biometrias:
        try:
            db_embedding = pickle.loads(bio.embedding)
            dist = calcular_distancia_embedding(db_embedding, embedding_actual)
            if dist < mejor_distancia:
                mejor_distancia = dist
                mejor_usuario = bio.usuario
        except Exception:
            continue

    if mejor_usuario is None or mejor_distancia > UMBRAL_MAXIMO:
        return Response(
            {"detail": "Rostro no reconocido en el sistema. Asegúrate de haberlo registrado previamente."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    usuario = mejor_usuario
    if not usuario.is_active:
        return Response(
            {"detail": "Esta cuenta se encuentra inactiva."},
            status=status.HTTP_403_FORBIDDEN
        )

    rol_obj = getattr(usuario, 'rol', None)
    rol_str = getattr(rol_obj, 'nombre', '') if rol_obj else ''
    rol_lower = rol_str.lower()
    email_lower = (usuario.correo or '').lower()
    es_admin = (
        usuario.is_superuser or
        'admin' in rol_lower or
        'super' in rol_lower or
        'supervisor' in rol_lower or
        'admin' in email_lower
    )

    if plataforma == 'movil' and es_admin:
        return Response(
            {
                "detail": (
                    f"Acceso restringido: El usuario {usuario.nombre} tiene rol administrativo ({rol_str}). "
                    "La aplicación móvil es de uso exclusivo para Manipuladoras y Jefas de cocina. "
                    "Por favor ingresa desde la plataforma Web."
                ),
                "rol": rol_str,
                "codigo": "ROL_NO_PERMITIDO_MOVIL"
            },
            status=status.HTTP_403_FORBIDDEN
        )

    if plataforma == 'web' and not es_admin and 'jefa' not in rol_lower and 'coordinad' not in rol_lower:
        return Response(
            {
                "detail": (
                    f"El usuario {usuario.nombre} tiene rol operativo ({rol_str}). "
                    "El personal manipulador de alimentos debe ingresar a través de la aplicación móvil institucional."
                ),
                "rol": rol_str,
                "codigo": "ROL_NO_PERMITIDO_WEB"
            },
            status=status.HTTP_403_FORBIDDEN
        )

    # Generar tokens de sesión JWT
    refresh = RefreshToken.for_user(usuario)
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
        "distancia": round(mejor_distancia, 4),
        "msg": f"Bienvenido(a) {usuario.nombre}"
    }, status=status.HTTP_200_OK)
