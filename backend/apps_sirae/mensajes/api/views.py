import os
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    cloudinary = None

from apps_sirae.usuarios.models import Usuario
from apps_sirae.mensajes.models import Mensaje
from apps_sirae.mensajes.permissions import (
    MENSAJE_ERROR_PERMISOS,
    puede_comunicarse,
    get_contactos_permitidos_para_usuario,
)
from apps_sirae.mensajes.api.serializers import (
    MensajeSerializer,
    ContactoChatSerializer,
)


class MensajeViewSet(viewsets.ModelViewSet):
    """
    ViewSet para la gestión completa de mensajería y chat con validación de matriz de comunicación.
    """
    queryset = Mensaje.objects.all().order_by('fecha_envio', 'id_mensaje')
    serializer_class = MensajeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Mensaje.objects.none()

        contacto_id = self.request.query_params.get('contacto') or self.request.query_params.get('destinatario')
        if contacto_id:
            try:
                contacto_id = int(contacto_id)
            except (ValueError, TypeError):
                return Mensaje.objects.none()

            # CA-09: Marcado automático de lectura al abrir la conversación
            Mensaje.objects.filter(
                remitente_id=contacto_id,
                destinatario=user,
                leido=False
            ).update(leido=True)

            # CA-08: Listar mensajes ordenados cronológicamente del más antiguo al más reciente
            return Mensaje.objects.filter(
                (Q(remitente=user, destinatario_id=contacto_id) |
                 Q(remitente_id=contacto_id, destinatario=user))
            ).select_related('remitente', 'destinatario', 'remitente__rol', 'destinatario__rol').order_by('fecha_envio', 'id_mensaje')

        # Si no se filtra por contacto, retornar mensajes donde participe el usuario
        return Mensaje.objects.filter(
            Q(remitente=user) | Q(destinatario=user)
        ).select_related('remitente', 'destinatario', 'remitente__rol', 'destinatario__rol').order_by('fecha_envio', 'id_mensaje')

    def create(self, request, *args, **kwargs):
        """
        Redirige la creación directa al método estandarizado de envío.
        """
        return self.enviar(request)

    @action(
        detail=False,
        methods=['post'],
        url_path='enviar',
        parser_classes=[JSONParser, FormParser, MultiPartParser],
    )
    def enviar(self, request):
        """
        Endpoint seguro de envío de mensajes con validación estricta de matriz de permisos (CA-01 a CA-05),
        soporte para subida de imágenes a Cloudinary (CA-07) y persistencia (CA-06).
        """
        remitente = request.user
        destinatario_raw = (
            request.data.get('destinatario')
            or request.data.get('id_destinatario')
            or request.data.get('destinatario_id')
        )

        if not destinatario_raw:
            return Response(
                {'error': 'El campo destinatario es obligatorio.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            destinatario_id = int(destinatario_raw)
        except (ValueError, TypeError):
            return Response(
                {'error': 'El identificador de destinatario no es válido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            destinatario = Usuario.objects.select_related('rol').get(
                id_usuario=destinatario_id,
                is_active=True
            )
        except Usuario.DoesNotExist:
            return Response(
                {'error': 'El destinatario especificado no existe o está inactivo.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # CA-05: Validación estricta de la matriz de comunicación por rol
        if not puede_comunicarse(remitente, destinatario):
            return Response(
                {
                    'error': MENSAJE_ERROR_PERMISOS,
                    'detail': MENSAJE_ERROR_PERMISOS,
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        contenido_texto = (request.data.get('contenido_texto') or request.data.get('texto') or request.data.get('mensaje') or '').strip()
        imagen_archivo = request.FILES.get('imagen') or request.FILES.get('archivo')
        imagen_url = (request.data.get('imagen_url') or '').strip() or None

        # CA-06: contenido_texto (opcional si se envía imagen), imagen_url (opcional si se envía texto)
        if not contenido_texto and not imagen_archivo and not imagen_url:
            return Response(
                {'error': 'Debes enviar al menos un texto o una imagen adjunta.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # CA-07: Procesamiento de imagen adjunta (.jpg, .jpeg, .png, máx. 5MB)
        if imagen_archivo:
            # Validar tamaño máximo: 5MB
            limite_tamano = 5 * 1024 * 1024
            if imagen_archivo.size > limite_tamano:
                return Response(
                    {'error': 'La imagen no puede superar los 5MB.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validar extensión
            nombre_archivo = imagen_archivo.name.lower()
            extensiones_permitidas = ('.jpg', '.jpeg', '.png')
            if not any(nombre_archivo.endswith(ext) for ext in extensiones_permitidas):
                return Response(
                    {'error': 'Formato no permitido. Solo se aceptan archivos .jpg, .jpeg o .png.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Validar Content-Type
            if imagen_archivo.content_type and not imagen_archivo.content_type.startswith('image/'):
                return Response(
                    {'error': 'El archivo adjunto no es una imagen válida.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Subida segura a Cloudinary
            if cloudinary and hasattr(cloudinary, 'uploader'):
                try:
                    resultado = cloudinary.uploader.upload(
                        imagen_archivo,
                        folder='sirae_mensajes/',
                        resource_type='image'
                    )
                    imagen_url = resultado.get('secure_url') or resultado.get('url')
                    if not imagen_url:
                        return Response(
                            {'error': 'No se pudo obtener el enlace seguro de Cloudinary.'},
                            status=status.HTTP_502_BAD_GATEWAY,
                        )
                except Exception as e:
                    return Response(
                        {'error': f'Error al subir imagen a Cloudinary: {str(e)}'},
                        status=status.HTTP_502_BAD_GATEWAY,
                    )
            else:
                return Response(
                    {'error': 'El servicio de Cloudinary no se encuentra disponible.'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )

        # CA-06: Almacenamiento seguro en BD
        with transaction.atomic():
            mensaje = Mensaje.objects.create(
                remitente=remitente,
                destinatario=destinatario,
                contenido_texto=contenido_texto if contenido_texto else None,
                imagen_url=imagen_url,
                fecha_envio=timezone.now(),
                leido=False,
            )

        serializer = self.get_serializer(mensaje, context={'request': request})
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='conversacion/(?P<contacto_id>[^/.]+)')
    def conversacion(self, request, contacto_id=None):
        """
        CA-08 & CA-09: Consulta el historial de conversación con un contacto específico,
        ordenado cronológicamente (más antiguo al más reciente) y marcando los mensajes pendientes como leídos.
        """
        user = request.user
        try:
            contacto_id = int(contacto_id)
        except (ValueError, TypeError):
            return Response(
                {'error': 'ID de contacto no válido.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            contacto = Usuario.objects.select_related('rol').get(
                id_usuario=contacto_id,
                is_active=True
            )
        except Usuario.DoesNotExist:
            return Response(
                {'error': 'El contacto no existe o no está activo.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # CA-09: Marcado automático de lectura
        Mensaje.objects.filter(
            remitente_id=contacto_id,
            destinatario=user,
            leido=False
        ).update(leido=True)

        # CA-08: Mensajes ordenados cronológicamente
        mensajes = Mensaje.objects.filter(
            (Q(remitente=user, destinatario_id=contacto_id) |
             Q(remitente_id=contacto_id, destinatario=user))
        ).select_related('remitente', 'destinatario', 'remitente__rol', 'destinatario__rol').order_by('fecha_envio', 'id_mensaje')

        serializer = self.get_serializer(mensajes, many=True, context={'request': request})
        return Response({
            'contacto': ContactoChatSerializer(contacto).data,
            'mensajes': serializer.data,
            'cantidad': mensajes.count()
        })

    @action(detail=False, methods=['get'], url_path='contactos')
    def contactos(self, request):
        """
        Retorna la lista de contactos permitidos según el rol del usuario logueado (CA-10),
        incluyendo el conteo de mensajes no leídos (CA-11) y el último mensaje intercambiado.
        """
        user = request.user
        contactos_qs = get_contactos_permitidos_para_usuario(user)

        lista_contactos = []
        for contacto in contactos_qs:
            # Contar no leídos de este contacto hacia el usuario
            no_leidos = Mensaje.objects.filter(
                remitente=contacto,
                destinatario=user,
                leido=False
            ).count()

            # Obtener el último mensaje entre ambos
            ultimo_msg = Mensaje.objects.filter(
                (Q(remitente=user, destinatario=contacto) |
                 Q(remitente=contacto, destinatario=user))
            ).order_by('-fecha_envio', '-id_mensaje').first()

            ultimo_texto = ''
            ultima_fecha = None
            if ultimo_msg:
                ultima_fecha = ultimo_msg.fecha_envio
                if ultimo_msg.contenido_texto:
                    ultimo_texto = ultimo_msg.contenido_texto
                elif ultimo_msg.imagen_url:
                    ultimo_texto = '📷 [Imagen]'

            lista_contactos.append({
                'id_usuario': contacto.id_usuario,
                'nombre': contacto.nombre,
                'apellido': contacto.apellido,
                'nombre_completo': f"{contacto.nombre} {contacto.apellido}".strip(),
                'correo': contacto.correo,
                'rol': contacto.rol.nombre if contacto.rol else '',
                'ultimo_mensaje': ultimo_texto,
                'ultima_fecha': ultima_fecha,
                'mensajes_no_leidos': no_leidos,
            })

        # Ordenar por fecha del último mensaje descendente, o nombre
        lista_contactos.sort(
            key=lambda c: (c['ultima_fecha'] is not None, c['ultima_fecha']),
            reverse=True
        )

        return Response(lista_contactos)

    @action(detail=False, methods=['get'], url_path='no-leidos')
    def no_leidos(self, request):
        """
        Retorna el conteo global de mensajes no leídos para el usuario logueado (CA-11).
        """
        user = request.user
        total = Mensaje.objects.filter(destinatario=user, leido=False).count()
        return Response({
            'total_no_leidos': total,
        })
