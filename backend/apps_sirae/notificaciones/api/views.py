
from django.db import transaction

from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

import cloudinary.uploader

from apps_sirae.usuarios.models import Usuario
from ..models import Notificacion
from .serializer import NotificacionSerializer


class notificacionesApiViewset(viewsets.ModelViewSet):
    queryset = Notificacion.objects.all().order_by(
        '-fecha_hora', '-id_notificacion'
    )
    serializer_class = NotificacionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        usuario_id = getattr(self.request.user, 'id_usuario', None)

        if usuario_id is None:
            return Notificacion.objects.none()

        return Notificacion.objects.filter(
            id_usuario=usuario_id
        ).order_by('-fecha_hora', '-id_notificacion')

    def create(self, request, *args, **kwargs):
        return Response(
            {
                'error': (
                    'Utiliza el endpoint enviar para crear '
                    'notificaciones con permisos por rol.'
                )
            },
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='enviar',
        parser_classes=[JSONParser, FormParser, MultiPartParser],
    )
    def enviar(self, request):
        remitente = request.user
        remitente_id = getattr(remitente, 'id_usuario', None)

        titulo = str(request.data.get('titulo', '')).strip()
        mensaje = str(request.data.get('mensaje', '')).strip()
        imagen = request.FILES.get('imagen')

        if not titulo or not mensaje:
            return Response(
                {'error': 'El título y el mensaje son obligatorios.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(titulo) > 150:
            return Response(
                {'error': 'El título no puede superar 150 caracteres.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if imagen:
            if (
                not imagen.content_type
                or not imagen.content_type.startswith('image/')
            ):
                return Response(
                    {'error': 'El archivo debe ser una imagen.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if imagen.size > 5 * 1024 * 1024:
                return Response(
                    {'error': 'La imagen no puede superar 5 MB.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        es_admin = remitente.es_administrador()
        es_supervisor = remitente.es_supervisor()
        es_manipuladora = remitente.es_manipuladora()
        es_jefa = remitente.es_jefa_manipuladoras()

        if es_admin:
            tipo_destino = 'supervisor'
        elif es_supervisor:
            tipo_destino = 'android'
        elif es_manipuladora or es_jefa:
            tipo_destino = 'coordinacion'
        else:
            return Response(
                {
                    'error': (
                        'Tu rol no tiene permiso para '
                        'enviar notificaciones.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        usuarios_activos = Usuario.objects.filter(
            is_active=True
        ).select_related('rol')

        if tipo_destino == 'supervisor':
            destinatarios = [
                usuario
                for usuario in usuarios_activos
                if (
                    usuario.es_supervisor()
                    and usuario.id_usuario != remitente_id
                )
            ]

        elif tipo_destino == 'android':
            destinatarios = [
                usuario
                for usuario in usuarios_activos
                if (
                    (
                        usuario.es_manipuladora()
                        or usuario.es_jefa_manipuladoras()
                    )
                    and usuario.id_usuario != remitente_id
                )
            ]

        else:
            destinatarios = [
                usuario
                for usuario in usuarios_activos
                if (
                    (
                        usuario.es_supervisor()
                        or usuario.es_administrador()
                    )
                    and usuario.id_usuario != remitente_id
                )
            ]

        if not destinatarios:
            return Response(
                {
                    'error': (
                        'No hay destinatarios activos '
                        'para tu rol.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        imagen_url = None

        if imagen:
            try:
                resultado = cloudinary.uploader.upload(
                    imagen,
                    folder='sirae_notificaciones/',
                    resource_type='image',
                )
                imagen_url = resultado.get('secure_url')

                if not imagen_url:
                    return Response(
                        {
                            'error': (
                                'No se pudo obtener la URL '
                                'de la imagen.'
                            )
                        },
                        status=status.HTTP_502_BAD_GATEWAY,
                    )

            except Exception:
                return Response(
                    {
                        'error': (
                            'No se pudo guardar la imagen. '
                            'Verifica la configuración de Cloudinary.'
                        )
                    },
                    status=status.HTTP_502_BAD_GATEWAY,
                )

        with transaction.atomic():
            creadas = Notificacion.objects.bulk_create([
                Notificacion(
                    id_usuario=destinatario.id_usuario,
                    id_remitente=remitente_id,
                    titulo=titulo,
                    mensaje=mensaje,
                    imagen_url=imagen_url,
                )
                for destinatario in destinatarios
            ])

        return Response(
            {
                'mensaje': 'Notificación enviada correctamente.',
                'cantidad_destinatarios': len(creadas),
                'resultados': self.get_serializer(
                    creadas,
                    many=True,
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=['get'],
        url_path='no-leidas',
    )
    def no_leidas(self, request):
        queryset = self.get_queryset().filter(leida=False)
        serializer = self.get_serializer(queryset, many=True)

        return Response({
            'cantidad': queryset.count(),
            'resultados': serializer.data,
        })

    @action(
        detail=True,
        methods=['post'],
        url_path='marcar-leida',
    )
    def marcar_leida(self, request, pk=None):
        notificacion = self.get_object()

        if not notificacion.leida:
            notificacion.leida = True
            notificacion.save(update_fields=['leida'])

        return Response(self.get_serializer(notificacion).data)

    @action(
        detail=False,
        methods=['post'],
        url_path='marcar-todas-leidas',
    )
    def marcar_todas_leidas(self, request):
        actualizadas = self.get_queryset().filter(
            leida=False
        ).update(leida=True)

        return Response(
            {
                'actualizadas': actualizadas,
                'mensaje': (
                    'Todas las notificaciones fueron '
                    'marcadas como leídas.'
                ),
            },
            status=status.HTTP_200_OK,
        )
