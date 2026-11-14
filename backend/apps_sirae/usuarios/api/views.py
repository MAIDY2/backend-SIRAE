from datetime import datetime, timezone as dt_timezone
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps_sirae.usuarios.models import AuditoriaUsuario, Usuario
from apps_sirae.usuarios.permissions import UsuarioConsultationAndScopePermission
from apps_sirae.usuarios.api.serializers import (
    UsuarioSerializer,
    UsuarioPerfilPropioSerializer,
    CustomTokenObtainPairSerializer,
    CustomTokenRefreshSerializer,
    revocar_sesiones_activas_usuario,
    instituciones_asignadas_del_supervisor,
)
from apps_sirae.usuarios.api.password_reset import (
    ConfirmarCodigoRecuperacionPasswordView,
    SolicitarCodigoRecuperacionPasswordView,
    SolicitarRecuperacionPasswordView,
    ConfirmarRecuperacionPasswordView,
    ValidarTokenPasswordView,
    CambiarPasswordView,
    PerfilUsuarioView,
    TestEmailView,
    enviar_email_brevo_api,
)


class UsuarioPagination(PageNumberPagination):
    """
    Criterio 10: Paginación configurable del lado del servidor para el listado de usuarios.
    """
    page_size = 100
    page_size_query_param = 'page_size'
    max_page_size = 500


class UsuarioViewSet(viewsets.ModelViewSet):
    queryset = Usuario.objects.select_related(
        'rol', 'id_institucion', 'id_sede', 'id_jornada', 'creado_por'
    ).order_by('id_usuario')
    serializer_class = UsuarioSerializer
    permission_classes = [IsAuthenticated, UsuarioConsultationAndScopePermission]
    pagination_class = UsuarioPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['nombre', 'apellido', 'numero_documento', 'correo']
    ordering_fields = ['id_usuario', 'nombre', 'apellido', 'correo', 'fecha_creacion']
    ordering = ['id_usuario']

    @staticmethod
    def _obtener_instituciones_asignadas_supervisor(user) -> set[int]:
        institucion_ids = set(
            user.instituciones_asignadas.values_list('id_institucion_id', flat=True)
        )
        try:
            from apps_sirae.contratos_pae.models import Contrato
            contratos_ids = Contrato.objects.filter(
                id_usuario_supervisor=user,
                id_institucion__isnull=False
            ).values_list('id_institucion_id', flat=True)
            institucion_ids.update(contratos_ids)
        except Exception:
            pass
        if user.id_institucion_id:
            institucion_ids.add(user.id_institucion_id)
        return {int(cid) for cid in institucion_ids if cid is not None}

    def _aplicar_filtros_busqueda(self, qs, user):
        params = self.request.query_params

        # Criterio 2: Búsqueda dinámica por nombre, apellido, número de documento o correo electrónico
        termino_busqueda = (
            params.get('search')
            or params.get('q')
            or ''
        ).strip()
        if termino_busqueda:
            partes = [p for p in termino_busqueda.split() if p]
            if len(partes) > 1:
                condicion_compuesta = Q()
                for palabra in partes:
                    condicion_compuesta &= (
                        Q(nombre__icontains=palabra)
                        | Q(apellido__icontains=palabra)
                        | Q(numero_documento__icontains=palabra)
                        | Q(correo__icontains=palabra)
                    )
                qs = qs.filter(
                    Q(nombre__icontains=termino_busqueda)
                    | Q(apellido__icontains=termino_busqueda)
                    | Q(numero_documento__icontains=termino_busqueda)
                    | Q(correo__icontains=termino_busqueda)
                    | condicion_compuesta
                )
            else:
                qs = qs.filter(
                    Q(nombre__icontains=termino_busqueda)
                    | Q(apellido__icontains=termino_busqueda)
                    | Q(numero_documento__icontains=termino_busqueda)
                    | Q(correo__icontains=termino_busqueda)
                )

        nombre_param = (params.get('nombre') or '').strip()
        if nombre_param:
            qs = qs.filter(
                Q(nombre__icontains=nombre_param)
                | Q(apellido__icontains=nombre_param)
            )

        doc_param = (
            params.get('numero_documento')
            or params.get('documento')
            or ''
        ).strip()
        if doc_param:
            qs = qs.filter(numero_documento__icontains=doc_param)

        correo_param = (
            params.get('correo')
            or params.get('email')
            or ''
        ).strip()
        if correo_param:
            qs = qs.filter(correo__icontains=correo_param)

        # Criterio 3: Filtrar por rol y por estado de la cuenta
        rol_param = (params.get('rol') or params.get('id_rol') or '').strip()
        if rol_param:
            if rol_param.isdigit():
                qs = qs.filter(rol_id=int(rol_param))
            else:
                qs = qs.filter(rol__nombre__iexact=rol_param)

        estado_param = params.get('estado')
        if estado_param is None:
            estado_param = params.get('is_active')
        if estado_param is not None and str(estado_param).strip() != '':
            estado_norm = str(estado_param).strip().lower()
            if estado_norm in {'bloqueado', 'bloqueada', 'locked'}:
                qs = qs.filter(is_active=True, bloqueado_hasta__gt=timezone.now())
            elif estado_norm in {'activo', 'activa', 'active', 'true', '1', 'yes', 'si', 'sí'}:
                qs = qs.filter(is_active=True)
            elif estado_norm in {'inactivo', 'inactiva', 'inactive', 'false', '0', 'no'}:
                qs = qs.filter(is_active=False)

        # Criterio 4: Filtrar por institución cuando corresponda al ámbito del usuario autenticado
        inst_param = (
            params.get('id_institucion')
            or params.get('institucion')
            or ''
        ).strip()
        if inst_param:
            if not inst_param.isdigit():
                return qs.none()
            inst_id = int(inst_param)

            # Si es Administrador institucional, nunca puede consultar otra institución fuera de la suya
            if user.es_administrador() and not (user.es_super_administrador() or user.is_superuser):
                if user.id_institucion_id != inst_id:
                    return qs.none()
                qs = qs.filter(id_institucion_id=inst_id)
            elif user.es_supervisor() and not (user.es_super_administrador() or user.is_superuser):
                inst_ids_sup = self._obtener_instituciones_asignadas_supervisor(user)
                if inst_id not in inst_ids_sup:
                    return qs.none()
                qs = qs.filter(id_institucion_id=inst_id)
            else:
                qs = qs.filter(
                    Q(id_institucion_id=inst_id)
                    | Q(instituciones_asignadas__id_institucion_id=inst_id)
                ).distinct()

        return qs

    def get_queryset(self):
        user = self.request.user
        if not user or not user.is_authenticated:
            return Usuario.objects.none()

        base_qs = Usuario.objects.select_related(
            'rol', 'id_institucion', 'id_sede', 'id_jornada', 'creado_por'
        ).order_by('id_usuario')

        # Criterio 5: El Superadministrador puede consultar y visualizar los usuarios
        # de todas las instituciones del sistema sin restricciones.
        if user.es_super_administrador() or user.is_superuser:
            return self._aplicar_filtros_busqueda(base_qs.all(), user)

        # Criterio 6: El Administrador institucional únicamente puede consultar usuarios
        # pertenecientes estrictamente a su propia institución y dentro de las facultades autorizadas.
        if user.es_administrador():
            if user.id_institucion_id:
                qs_admin = base_qs.filter(
                    id_institucion_id=user.id_institucion_id,
                    is_superuser=False,
                ).exclude(
                    rol__nombre__icontains='super'
                )
                return self._aplicar_filtros_busqueda(qs_admin, user)
            return self._aplicar_filtros_busqueda(
                base_qs.filter(id_usuario=user.id_usuario),
                user
            )

        # Criterio 7: El Supervisor únicamente puede consultar información de usuarios
        # cuando una funcionalidad específica y explícita se lo permita.
        if user.es_supervisor():
            funcionalidad = (
                self.request.query_params.get('funcionalidad')
                or self.request.query_params.get('contexto')
                or self.request.query_params.get('ambito')
                or ''
            ).strip().lower()
            es_accion_explicita = getattr(self, 'action', '') == 'consulta_supervision'

            if es_accion_explicita or funcionalidad in {
                'supervision_pae',
                'supervision_institucional',
                'instituciones_asignadas',
                'equipo_institucional',
            }:
                inst_ids = self._obtener_instituciones_asignadas_supervisor(user)
                if not inst_ids:
                    return base_qs.filter(id_usuario=user.id_usuario)
                qs_sup = base_qs.filter(
                    Q(id_institucion_id__in=inst_ids)
                    | Q(id_usuario=user.id_usuario),
                    is_superuser=False,
                ).exclude(
                    rol__nombre__icontains='super'
                )
                return self._aplicar_filtros_busqueda(qs_sup, user)

            # Sin funcionalidad explícita autorizada, el Supervisor solo puede ver su propio perfil
            return self._aplicar_filtros_busqueda(
                base_qs.filter(id_usuario=user.id_usuario),
                user
            )

        # Los demás roles solo pueden ver su propio perfil
        return self._aplicar_filtros_busqueda(
            base_qs.filter(id_usuario=user.id_usuario),
            user
        )

    @action(detail=False, methods=['get'], url_path='consulta-supervision')
    def consulta_supervision(self, request):
        """
        Criterio 7: Funcionalidad explícita para que un Supervisor consulte el personal
        adscrito exclusivamente a las instituciones bajo su supervisión.
        """
        user = request.user
        if not (user.es_supervisor() or user.es_super_administrador() or user.is_superuser):
            raise PermissionDenied(
                'Solo el Supervisor o Super Administrador pueden acceder a esta consulta de supervisión.'
            )
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['patch', 'post'], url_path='cambiar-estado')
    def cambiar_estado(self, request, pk=None):
        """
        Criterios 3, 5, 7, 9 y 10: Endpoint dedicado para activar o desactivar
        una cuenta de usuario con validación de alcance, restricción de autogestión,
        revocación inmediata de tokens activos y registro formal en AuditoriaUsuario.
        """
        user = request.user
        if not (user and user.is_authenticated and (user.es_super_administrador() or user.is_superuser or user.es_administrador())):
            raise PermissionDenied('Tu rol no tiene autorización para activar o desactivar cuentas de usuario.')

        instance = self.get_object()

        # Criterio 10: Restricción de Autogestión
        if instance.id_usuario == user.id_usuario:
            raise PermissionDenied('No tienes autorización para activar o desactivar tu propia cuenta.')

        if instance.es_super_administrador() or instance.is_superuser:
            raise PermissionDenied('La cuenta del Super Administrador no puede ser desactivada.')

        if user.es_administrador() and not (user.es_super_administrador() or user.is_superuser):
            if (
                not user.id_institucion_id
                or instance.id_institucion_id != user.id_institucion_id
                or instance.es_supervisor()
                or instance.es_administrador()
            ):
                raise PermissionDenied(
                    'No tienes autorización para cambiar el estado de usuarios fuera de tu ámbito institucional.'
                )

        payload = {}
        if isinstance(request.data, dict):
            if 'is_active' in request.data:
                payload['is_active'] = request.data.get('is_active')
            elif 'estado' in request.data:
                payload['estado'] = request.data.get('estado')
        if not payload:
            payload['is_active'] = not bool(instance.is_active)

        serializer = self.get_serializer(instance, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='auditoria')
    def auditoria(self, request, pk=None):
        """
        Criterio 9: Consulta de la bitácora de auditoría de un usuario específico.
        """
        user = request.user
        if not (user and user.is_authenticated and (user.es_super_administrador() or user.is_superuser or user.es_administrador())):
            raise PermissionDenied('Solo usuarios administrativos pueden consultar la bitácora de auditoría.')

        instance = self.get_object()
        registros = AuditoriaUsuario.objects.filter(
            usuario_afectado=instance
        ).select_related('usuario_actor').order_by('-creado_en')

        data = [
            {
                'id_auditoria': reg.id_auditoria,
                'usuario_afectado': reg.usuario_afectado_id,
                'usuario_actor': reg.usuario_actor_id,
                'usuario_actor_correo': reg.usuario_actor.correo if reg.usuario_actor else 'Sistema',
                'usuario_actor_nombre': reg.usuario_actor.nombre_completo if reg.usuario_actor else 'Sistema',
                'accion': reg.accion,
                'estado_anterior': reg.estado_anterior,
                'estado_nuevo': reg.estado_nuevo,
                'detalle': reg.detalle,
                'ip_address': reg.ip_address,
                'creado_en': reg.creado_en,
            }
            for reg in registros
        ]
        return Response(data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get', 'put', 'patch'], url_path='me')
    def me(self, request):
        """
        Criterios 1, 4 y 5: Visualización y Edición de Datos Propios del Perfil (Autogestión).
        GET: Retorna los datos actuales del perfil del usuario autenticado.
        PUT / PATCH: Permite al usuario común actualizar sus propios datos personales autorizados
                     (nombre, apellido), aplicando validaciones y rechazando/ignorando campos protegidos.
        """
        user = request.user
        if not (user and user.is_authenticated):
            raise PermissionDenied('No autenticado.')
        if not user.is_active:
            raise PermissionDenied('Tu cuenta se encuentra inactiva o sin autorización vigente.')

        if request.method == 'GET':
            serializer = UsuarioPerfilPropioSerializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)

        # Criterio 5: Restricción estricta de campos protegidos
        serializer = UsuarioPerfilPropioSerializer(
            user,
            data=request.data,
            partial=(request.method == 'PATCH'),
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        # Registro de auditoría de autogestión de perfil
        try:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR') if hasattr(request, 'META') else None
            ip_cliente = (
                x_forwarded_for.split(',')[0].strip()
                if x_forwarded_for
                else (request.META.get('REMOTE_ADDR') if hasattr(request, 'META') else None)
            )
            AuditoriaUsuario.objects.create(
                usuario_afectado=user,
                usuario_actor=user,
                accion='EDICION_PERFIL',
                estado_anterior='Activo',
                estado_nuevo='Activo',
                detalle=f"Autogestión de perfil: usuario actualizó sus datos personales (nombre: {user.nombre}, apellido: {user.apellido}).",
                ip_address=ip_cliente,
            )
        except Exception:
            pass

        return Response(serializer.data, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        user = self.request.user
        if not (user.es_super_administrador() or user.is_superuser or user.es_administrador()):
            raise PermissionDenied('Tu rol no tiene autorización para registrar usuarios.')
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        instance = self.get_object()
        if not (user.es_super_administrador() or user.is_superuser):
            if instance.id_usuario == user.id_usuario:
                # El usuario está modificando su propio perfil desde la ruta de detalle:
                # Criterio 5: Bloquear estrictamente cualquier intento de alterar campos protegidos
                campos_restringidos = {'rol', 'is_active', 'estado', 'id_institucion', 'id_sede', 'correo', 'email'}
                if any(campo in self.request.data for campo in campos_restringidos):
                    raise PermissionDenied('No tienes autorización para modificar tu propio rol, estado, correo o asignaciones institucionales.')
            elif user.es_administrador():
                if (
                    not user.id_institucion_id
                    or instance.id_institucion_id != user.id_institucion_id
                    or instance.es_super_administrador()
                    or instance.is_superuser
                ):
                    raise PermissionDenied('No tienes permisos para modificar usuarios fuera de tu institución.')
            else:
                raise PermissionDenied('Tu rol no tiene autorización para modificar usuarios.')
        serializer.save()

    def perform_destroy(self, instance):
        """
        Criterio 7: Integridad Histórica.
        Nunca se elimina físicamente el registro de un usuario; al invocar DELETE
        se realiza únicamente la desactivación lógica conservando intactas todas
        las relaciones institucionales, bitácoras y registros históricos.
        """
        user = self.request.user
        if instance.es_super_administrador() or instance.is_superuser:
            raise PermissionDenied('El Super Administrador no puede ser desactivado ni eliminado del sistema.')
        if instance.id_usuario == user.id_usuario:
            raise PermissionDenied('No tienes autorización para desactivar o eliminar tu propia cuenta.')
        if not (user.es_super_administrador() or user.is_superuser):
            if user.es_administrador():
                if (
                    not user.id_institucion_id
                    or instance.id_institucion_id != user.id_institucion_id
                    or instance.es_supervisor()
                    or instance.es_administrador()
                ):
                    raise PermissionDenied('No tienes permisos para desactivar usuarios fuera de tu institución.')
            else:
                raise PermissionDenied('Tu rol no tiene autorización para desactivar usuarios.')

        estado_anterior = 'Activo' if instance.is_active else 'Inactivo'
        instance.is_active = False
        instance.save(update_fields=['is_active', 'fecha_actualizacion'])
        revocar_sesiones_activas_usuario(instance)

        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR') if hasattr(self.request, 'META') else None
        ip_cliente = (
            x_forwarded_for.split(',')[0].strip()
            if x_forwarded_for
            else (self.request.META.get('REMOTE_ADDR') if hasattr(self.request, 'META') else None)
        )
        AuditoriaUsuario.objects.create(
            usuario_afectado=instance,
            usuario_actor=user,
            accion='DESACTIVACION',
            estado_anterior=estado_anterior,
            estado_nuevo='Inactivo',
            detalle=(
                f"Desactivación lógica de cuenta de usuario '{instance.correo}': "
                f"estado anterior '{estado_anterior}', estado nuevo 'Inactivo'."
            ),
            ip_address=ip_cliente,
        )


class RegistroView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = UsuarioSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            usuario = serializer.save()
            return Response(
                {
                    'mensaje': 'Usuario registrado exitosamente',
                    'data': UsuarioSerializer(usuario, context={'request': request}).data
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


import logging
logger = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenObtainPairSerializer

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            logger.error("[SIRAE LOGIN ERROR]: %s\n%s", e, tb)
            return Response(
                {
                    "error": "Error interno en login",
                    "detalle": str(e),
                    "tipo": e.__class__.__name__,
                    "traceback": [line.strip() for line in tb.splitlines()[-6:]],
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class MigrarDBView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        import io
        from django.core.management import call_command
        out = io.StringIO()
        err = io.StringIO()
        try:
            call_command('migrate', stdout=out, stderr=err, interactive=False)
            res = "ok"
            status_code = status.HTTP_200_OK
        except Exception as e:
            import traceback
            res = f"error: {e}"
            err.write(traceback.format_exc())
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        return Response({
            "status": res,
            "stdout": [l for l in out.getvalue().splitlines() if l.strip()],
            "stderr": [l for l in err.getvalue().splitlines() if l.strip()],
            "version": "2026-11-14-login-fix"
        }, status=status_code)


class CustomTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    serializer_class = CustomTokenRefreshSerializer


class LogoutView(APIView):
    permission_classes = [AllowAny]

    @staticmethod
    def _revocar_token_jti(token_obj, user=None):
        jti = token_obj.get('jti')
        if not jti:
            return

        exp = token_obj.get('exp')
        ahora_ts = int(timezone.now().timestamp())
        ttl = max(60, (int(exp) - ahora_ts) if exp else 86400)
        cache.set(f"revoked_jti:{jti}", True, timeout=ttl)

        expires_at = (
            datetime.fromtimestamp(int(exp), tz=dt_timezone.utc)
            if exp
            else timezone.now()
        )
        user_instance = user if (user and getattr(user, 'is_authenticated', False)) else None
        if not user_instance:
            user_id = token_obj.get('user_id') or token_obj.get('id_usuario')
            if user_id:
                user_instance = Usuario.objects.filter(id_usuario=user_id).first()

        outstanding, _ = OutstandingToken.objects.get_or_create(
            jti=jti,
            defaults={
                'user': user_instance,
                'token': str(token_obj),
                'created_at': timezone.now(),
                'expires_at': expires_at,
            },
        )
        BlacklistedToken.objects.get_or_create(token=outstanding)

    def _revocar_access_token_actual(self, request):
        user = getattr(request, 'user', None)
        auth_token = getattr(request, 'auth', None)
        if auth_token is not None and hasattr(auth_token, 'get'):
            self._revocar_token_jti(auth_token, user=user)
            return True

        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        raw_access = request.data.get('access') if hasattr(request.data, 'get') else None
        if not raw_access and auth_header.startswith('Bearer '):
            raw_access = auth_header.split(' ', 1)[1].strip()

        if raw_access:
            try:
                access_obj = AccessToken(raw_access)
                self._revocar_token_jti(access_obj, user=user)
                return True
            except TokenError:
                return False

        return False

    def post(self, request):
        refresh_token = request.data.get('refresh') if hasattr(request.data, 'get') else None
        access_revocado = self._revocar_access_token_actual(request)

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                self._revocar_token_jti(token, user=getattr(request, 'user', None))
                token.blacklist()
            except TokenError:
                return Response(
                    {'detail': 'El token de refresco es inválido o ya fue revocado.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response(
                {'mensaje': 'Sesión cerrada correctamente.'},
                status=status.HTTP_200_OK,
            )

        if access_revocado:
            user = getattr(request, 'user', None)
            if user and getattr(user, 'is_authenticated', False):
                for outstanding in OutstandingToken.objects.filter(user=user):
                    BlacklistedToken.objects.get_or_create(token=outstanding)
            return Response(
                {'mensaje': 'Sesión cerrada correctamente.'},
                status=status.HTTP_200_OK,
            )

        return Response(
            {'detail': 'Se requiere un token válido para cerrar la sesión.'},
            status=status.HTTP_400_BAD_REQUEST,
        )


class ValidarSesionActivaView(APIView):
    """
    Criterios 1, 3, 4 y 5: Validación activa y comprobación de vigencia del token contra el backend.
    Endpoint `/api/auth/verify/` y `/api/auth/validar-sesion/`.
    Comprueba que el token JWT sea válido, no revocado y vigente, y que el usuario se encuentre activo.
    Retorna el estado de validez y la información de usuario estrictamente sanitizada (Cero contraseñas).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        if not user or not user.is_authenticated or not user.is_active:
            return Response(
                {
                    'valido': False,
                    'detail': 'La sesión ha expirado, fue revocada o la cuenta se encuentra inactiva.',
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        rol_cliente = CustomTokenObtainPairSerializer._rol_para_cliente(user)
        inst_nombre = (
            user.id_institucion.nombre_institucion
            if user.id_institucion else None
        )
        instituciones_sup = instituciones_asignadas_del_supervisor(user)
        if not inst_nombre and instituciones_sup:
            inst_nombre = instituciones_sup[0]['nombre_institucion']

        sede_nombre = user.id_sede.nombre_sede if user.id_sede else None

        return Response(
            {
                'valido': True,
                'usuario': {
                    'id_usuario': user.id_usuario,
                    'nombre': user.nombre,
                    'apellido': user.apellido,
                    'correo': user.correo,
                    'numero_documento': user.numero_documento,
                    'rol': rol_cliente,
                    'estado': 'Activo' if user.is_active else 'Inactivo',
                    'is_active': bool(user.is_active),
                    'id_institucion': user.id_institucion_id,
                    'institucion': inst_nombre,
                    'institucion_nombre': inst_nombre,
                    'id_sede': user.id_sede_id,
                    'sede_nombre': sede_nombre,
                    'instituciones_supervisor': instituciones_sup,
                    'is_superuser': bool(user.is_superuser),
                    'debe_cambiar_password': bool(
                        getattr(user, 'debe_cambiar_password', False)
                    ),
                },
            },
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        return self.get(request)


RecuperarPasswordView = SolicitarCodigoRecuperacionPasswordView
