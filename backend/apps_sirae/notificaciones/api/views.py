
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
    pagination_class = None

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

            if imagen.size > 15 * 1024 * 1024:
                return Response(
                    {'error': 'La imagen no puede superar 15 MB.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        es_admin = remitente.es_administrador()
        es_supervisor = remitente.es_supervisor()
        es_jefa = remitente.es_jefa_manipuladoras()
        es_manipuladora = remitente.es_manipuladora()

        if not (es_admin or es_supervisor or es_jefa or es_manipuladora):
            return Response(
                {
                    'error': (
                        'Solo el administrador, el supervisor '
                        'la Jefa de Manipuladoras y la Manipuladora '
                        'pueden enviar '
                        'notificaciones.'
                    )
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        usuarios_activos = Usuario.objects.filter(
            is_active=True
        ).select_related('rol')

        if es_admin:
            destinatarios = [
                usuario
                for usuario in usuarios_activos
                if (
                    usuario.es_supervisor()
                    and usuario.id_usuario != remitente_id
                )
            ]
        elif es_jefa:
            destinatarios = [
                usuario
                for usuario in usuarios_activos
                if (
                    (usuario.es_supervisor() or usuario.es_administrador())
                    and usuario.id_usuario != remitente_id
                )
            ]
        elif es_manipuladora:
            destinatario_id = request.data.get('id_destinatario')

            if not destinatario_id:
                return Response(
                    {
                        'error': (
                            'Selecciona el supervisor como '
                            'destinatario.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                destinatario_id = int(destinatario_id)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'El destinatario seleccionado no es válido.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            destinatario = next(
                (
                    usuario
                    for usuario in usuarios_activos
                    if usuario.id_usuario == destinatario_id
                    and usuario.es_supervisor()
                ),
                None,
            )

            if destinatario is None:
                return Response(
                    {
                        'error': (
                            'La Manipuladora solo puede enviar '
                            'notificaciones al supervisor.'
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            destinatarios = [destinatario]
        else:
            destinatario_id = request.data.get('id_destinatario')

            if not destinatario_id:
                return Response(
                    {
                        'error': (
                            'Selecciona el administrador o la '
                            'Jefa de Manipuladoras como destinatario.'
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                destinatario_id = int(destinatario_id)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'El destinatario seleccionado no es válido.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            destinatario = next(
                (
                    usuario
                    for usuario in usuarios_activos
                    if usuario.id_usuario == destinatario_id
                    and (
                        usuario.es_administrador()
                        or usuario.es_jefa_manipuladoras()
                        or (
                            usuario.es_manipuladora()
                            and Notificacion.objects.filter(
                                id_usuario=remitente_id,
                                id_remitente=usuario.id_usuario,
                            ).exists()
                        )
                    )
                ),
                None,
            )

            if destinatario is None:
                return Response(
                    {
                        'error': (
                            'Solo puedes enviar al administrador '
                            'o a la Jefa de Manipuladoras, o responder '
                            'a una Manipuladora que te haya escrito.'
                        )
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )

            destinatarios = [destinatario]

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

        # Enviar correos de forma segura (fuera de la transacción atómica)
        from apps_sirae.notificaciones.services import notificar_usuarios_por_correo

        resultado_envio = notificar_usuarios_por_correo(
            destinatarios=destinatarios,
            remitente=remitente,
            titulo=titulo,
            mensaje=mensaje,
            imagen_url=imagen_url,
        )

        return Response(
            {
                'mensaje': 'Notificación enviada correctamente.',
                'cantidad_destinatarios': len(creadas),
                'correo_notificado': resultado_envio.get('exito', False),
                'resultados': self.get_serializer(
                    creadas,
                    many=True,
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='destinatarios')
    def destinatarios(self, request):
        remitente = request.user
        remitente_id = getattr(remitente, 'id_usuario', None)

        if remitente.es_administrador():
            permitido = lambda u: u.es_supervisor()
        elif remitente.es_jefa_manipuladoras():
            permitido = lambda u: u.es_supervisor() or u.es_administrador()
        elif remitente.es_supervisor():
            manipuladoras_que_escribieron = set(
                Notificacion.objects.filter(
                    id_usuario=remitente_id,
                    id_remitente__isnull=False,
                ).values_list('id_remitente', flat=True)
            )
            permitido = lambda u: (
                u.es_administrador()
                or u.es_jefa_manipuladoras()
                or (
                    u.es_manipuladora()
                    and u.id_usuario in manipuladoras_que_escribieron
                )
            )
        elif remitente.es_manipuladora():
            permitido = lambda u: u.es_supervisor()
        else:
            return Response(
                {'error': 'Tu rol no puede enviar notificaciones.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        usuarios = Usuario.objects.filter(
            is_active=True
        ).select_related('rol')

        return Response([
            {
                'id_usuario': u.id_usuario,
                'nombre': u.nombre_completo,
                'rol': u.rol.nombre if u.rol else '',
            }
            for u in usuarios
            if permitido(u) and u.id_usuario != remitente_id
        ])

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

    @action(
        detail=False,
        methods=['post'],
        url_path='alerta-inventario',
    )
    def alerta_inventario(self, request):
        """
        Dispara una alerta de inventario por stock bajo/agotado vía notificación y correo.
        Accesible por Administrador, Supervisor o Jefa de Manipuladoras.
        """
        usuario = request.user
        if not (
            usuario.es_administrador()
            or usuario.es_supervisor()
            or usuario.es_jefa_manipuladoras()
        ):
            return Response(
                {'error': 'No tienes permisos para emitir alertas de inventario.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        ingrediente = str(request.data.get('ingrediente', '')).strip()
        sede = str(request.data.get('sede', '')).strip()
        stock_actual = request.data.get('stock_actual')
        stock_minimo = request.data.get('stock_minimo')
        unidad = str(request.data.get('unidad', '')).strip()

        if not ingrediente or not sede or stock_actual is None or stock_minimo is None:
            return Response(
                {
                    'error': (
                        'Los campos ingrediente, sede, stock_actual '
                        'y stock_minimo son obligatorios.'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps_sirae.notificaciones.services import enviar_alerta_stock_inventario

        resultado = enviar_alerta_stock_inventario(
            ingrediente_nombre=ingrediente,
            sede_nombre=sede,
            stock_actual=stock_actual,
            stock_minimo=stock_minimo,
            unidad_medida=unidad,
            id_remitente=getattr(usuario, 'id_usuario', None),
        )

        return Response(
            {
                'mensaje': 'Alerta de inventario emitida correctamente.',
                'resultado_correo': resultado,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=False,
        methods=['post'],
        url_path='probar-email',
    )
    def probar_email(self, request):
        """
        Endpoint seguro (solo Administrador) para diagnosticar y probar el envío SMTP real con Gmail.
        """
        if not request.user.es_administrador():
            return Response(
                {'error': 'Solo el administrador puede probar el servicio de correo.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        email_destino = str(request.data.get('email', '')).strip()
        if not email_destino or '@' not in email_destino:
            return Response(
                {'error': 'Indica un correo electrónico válido en el campo email.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps_sirae.notificaciones.services import (
            construir_plantilla_notificacion_html,
            enviar_correo_notificacion,
        )

        asunto = 'Prueba de Conexión de Correo - SIRAE PAE'
        mensaje_texto = (
            'Hola,\n\n'
            'Este es un mensaje de prueba emitido desde la API de SIRAE PAE.\n'
            'Si lo recibiste, la configuración SMTP con Google está operando correctamente.'
        )
        mensaje_html = construir_plantilla_notificacion_html(
            titulo='Prueba de Conexión Exitosa',
            mensaje='Si estás leyendo este correo, la configuración SMTP de Google en SIRAE PAE está operando correctamente.',
            remitente_nombre=request.user.nombre_completo,
            remitente_rol='Administrador',
            categoria='DIAGNÓSTICO SMTP',
        )

        resultado = enviar_correo_notificacion(
            asunto=asunto,
            destinatarios=[email_destino],
            mensaje_texto=mensaje_texto,
            mensaje_html=mensaje_html,
        )

        return Response(
            {
                'mensaje': 'Diagnóstico de envío finalizado.',
                'resultado': resultado,
            },
            status=(
                status.HTTP_200_OK
                if resultado.get('exito')
                else status.HTTP_502_BAD_GATEWAY
            ),
        )
