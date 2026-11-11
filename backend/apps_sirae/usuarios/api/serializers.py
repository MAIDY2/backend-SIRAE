from datetime import datetime, timedelta, timezone as dt_timezone
import re
import secrets
import string
import unicodedata
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.cache import cache
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer, TokenRefreshSerializer
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from apps_sirae.instituciones.models import Institucion, SupervisorInstitucion
from apps_sirae.roles.api.serializers import RolSerializer
from apps_sirae.usuarios.models import AuditoriaUsuario, IntentoAutenticacion, Usuario


def registrar_token_emitido(token_obj, usuario: Usuario):
    """
    Registra un token JWT (Access o Refresh) en OutstandingToken para que pueda
    ser revocado e incluido en BlacklistedToken al desactivar la cuenta o cerrar sesión.
    """
    if not token_obj or not usuario or not getattr(usuario, 'pk', None):
        return None
    jti = token_obj.get('jti') if hasattr(token_obj, 'get') else None
    if not jti:
        return None
    exp = token_obj.get('exp')
    expires_at = (
        datetime.fromtimestamp(int(exp), tz=dt_timezone.utc)
        if exp
        else (timezone.now() + timedelta(hours=1))
    )
    outstanding, _ = OutstandingToken.objects.get_or_create(
        jti=jti,
        defaults={
            'user': usuario,
            'token': str(token_obj),
            'created_at': timezone.now(),
            'expires_at': expires_at,
        },
    )
    return outstanding


def revocar_sesiones_activas_usuario(usuario: Usuario) -> int:
    """
    Criterio 5: Invalida y revoca de inmediato todos los tokens activos
    (Refresh y Access tokens) asociados al usuario añadiéndolos a la lista negra
    (BlacklistedToken) de SimpleJWT y a la caché de tokens revocados.
    """
    if not usuario or not getattr(usuario, 'pk', None):
        return 0

    ahora_ts = int(timezone.now().timestamp())
    tokens_usuario = OutstandingToken.objects.filter(user=usuario)
    total_revocados = 0
    for outstanding in tokens_usuario:
        _, creado = BlacklistedToken.objects.get_or_create(token=outstanding)
        if outstanding.jti:
            exp_ts = (
                int(outstanding.expires_at.timestamp())
                if outstanding.expires_at
                else (ahora_ts + 86400)
            )
            ttl = max(60, exp_ts - ahora_ts)
            cache.set(f"revoked_jti:{outstanding.jti}", True, timeout=ttl)
        if creado:
            total_revocados += 1
    return total_revocados


def _normalizar_texto_rol(nombre: str) -> str:
    if not nombre:
        return ''
    return ' '.join(
        ''.join(
            c for c in unicodedata.normalize('NFD', str(nombre))
            if unicodedata.category(c) != 'Mn'
        ).strip().lower().split()
    )


def _es_rol_superadmin(rol_norm: str) -> bool:
    return rol_norm in {'superadministrador', 'super administrador', 'super admin'}


def _es_rol_admin_institucional(rol_norm: str) -> bool:
    return (
        rol_norm in {'administrador', 'admin', 'administrador institucional'}
        or ('admin' in rol_norm and 'super' not in rol_norm)
    )


def _es_rol_supervisor(rol_norm: str) -> bool:
    return (
        rol_norm in {'supervisor', 'coordinador', 'coordinador pae', 'supervisor pae'}
        or 'supervisor' in rol_norm
        or 'coordinador' in rol_norm
    )


def _es_rol_cocina(rol_norm: str) -> bool:
    return any(p in rol_norm for p in ('manipuladora', 'jefa', 'cocina'))


def generar_password_temporal_segura(longitud: int = 14) -> str:
    """
    Genera una contraseña temporal criptográficamente segura que cumple con
    complejidad de mayúsculas, minúsculas, dígitos y símbolos especiales.
    """
    longitud = max(12, int(longitud))
    mayusculas = string.ascii_uppercase
    minusculas = string.ascii_lowercase
    digitos = string.digits
    simbolos = '!@#$%&*+-='
    obligatorios = [
        secrets.choice(mayusculas),
        secrets.choice(minusculas),
        secrets.choice(digitos),
        secrets.choice(simbolos),
    ]
    alfabeto = mayusculas + minusculas + digitos + simbolos
    resto = [secrets.choice(alfabeto) for _ in range(longitud - len(obligatorios))]
    combinados = obligatorios + resto
    secrets.SystemRandom().shuffle(combinados)
    return ''.join(combinados)


def enviar_correo_activacion_cuenta(usuario: Usuario) -> bool:
    """
    Dispara un correo de activación/configuración inicial de contraseña usando
    un token firmado criptográficamente (jamás envía contraseñas en texto plano).
    """
    try:
        from apps_sirae.usuarios.api.password_reset import PasswordResetService

        token = PasswordResetService.generar_token(usuario)
        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:4200')
        enlace_activacion = f"{frontend_url}/recuperar-password?{urlencode({'token': token})}"

        send_mail(
            subject="Activación de cuenta y configuración de clave - SIRAE PAE",
            message=(
                f"Hola {usuario.nombre_completo},\n\n"
                "Tu cuenta institucional en SIRAE PAE ha sido creada.\n"
                "Por seguridad, nunca enviamos contraseñas en texto plano. "
                "Para activar tu acceso y definir tu contraseña personal, "
                f"ingresa al siguiente enlace seguro:\n{enlace_activacion}\n\n"
                "Si no reconoces este registro, ignora este mensaje."
            ),
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@sirae.edu.co'),
            recipient_list=[usuario.correo],
            fail_silently=True,
        )
        return True
    except Exception:
        return False


def instituciones_asignadas_del_supervisor(usuario):
    """
    Devuelve únicamente las instituciones asignadas al supervisor:
    por relación directa, contrato o institución principal.
    """
    if not usuario.es_supervisor():
        return []

    from apps_sirae.contratos_pae.models import Contrato

    institucion_ids = set(
        usuario.instituciones_asignadas.values_list(
            'id_institucion_id',
            flat=True
        )
    )

    institucion_ids.update(
        Contrato.objects.filter(
            id_usuario_supervisor=usuario,
            id_institucion__isnull=False
        ).values_list('id_institucion_id', flat=True)
    )

    if usuario.id_institucion_id:
        institucion_ids.add(usuario.id_institucion_id)

    if not institucion_ids:
        return []

    instituciones = (
        Institucion.objects.filter(pk__in=institucion_ids)
        .prefetch_related('sedes')
        .order_by('id_institucion')
    )

    return [
        {
            'id_institucion': institucion.id_institucion,
            'nombre_institucion': institucion.nombre_institucion,
            'nit': getattr(institucion, 'nit', ''),
            'sedes': [
                {
                    'id_sede': sede.id_sede,
                    'nombre_sede': sede.nombre_sede,
                    'codigo_dane': getattr(sede, 'codigo_dane', None),
                    'direccion': getattr(sede, 'direccion', None),
                }
                for sede in institucion.sedes.all()
            ],
            'representante_legal': getattr(
                institucion, 'representante_legal', None
            ),
            'telefono': getattr(institucion, 'telefono', None),
            'correo_contacto': getattr(institucion, 'correo_contacto', None),
            'estado': getattr(institucion, 'estado', None),
        }
        for institucion in instituciones
    ]


class UsuarioPerfilPropioSerializer(serializers.ModelSerializer):
    """
    Criterios 1, 4 y 5: Serializer exclusivo para la autogestión de perfil propio.
    Permite únicamente la modificación de datos personales autorizados (nombre, apellido)
    con validaciones de formato robustas (mínimo 2 caracteres, solo letras y espacios).
    Bloquea de forma terminante la modificación de campos protegidos:
    rol, estado (is_active), sede, correo institucional, institución, documento, horario o vigencia.
    Cualquier intento de alteración de estos campos es estrictamente ignorado o rechazado.
    """
    CAMPOS_PROTEGIDOS = {
        'rol', 'id_rol', 'is_active', 'estado', 'id_institucion', 'institucion',
        'id_sede', 'sede', 'correo', 'email', 'tipo_documento', 'numero_documento',
        'is_staff', 'is_superuser', 'debe_cambiar_password', 'bloqueado_hasta',
        'intentos_fallidos_login', 'creado_por', 'fecha_creacion', 'fecha_actualizacion',
        'horario', 'turno', 'vigencia_contrato', 'contrato',
    }

    nombre_completo = serializers.CharField(read_only=True)
    rol_nombre = serializers.SerializerMethodField(read_only=True)
    institucion_nombre = serializers.SerializerMethodField(read_only=True)
    sede_nombre = serializers.SerializerMethodField(read_only=True)
    instituciones_supervisor = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id_usuario',
            'nombre',
            'apellido',
            'nombre_completo',
            'correo',
            'tipo_documento',
            'numero_documento',
            'rol_nombre',
            'id_institucion',
            'institucion_nombre',
            'id_sede',
            'sede_nombre',
            'instituciones_supervisor',
            'is_active',
            'is_superuser',
            'debe_cambiar_password',
        ]
        read_only_fields = [
            'id_usuario',
            'nombre_completo',
            'correo',
            'tipo_documento',
            'numero_documento',
            'rol_nombre',
            'id_institucion',
            'institucion_nombre',
            'id_sede',
            'sede_nombre',
            'instituciones_supervisor',
            'is_active',
            'is_superuser',
            'debe_cambiar_password',
        ]

    def get_rol_nombre(self, obj):
        return CustomTokenObtainPairSerializer._rol_para_cliente(obj)

    def get_institucion_nombre(self, obj):
        return obj.id_institucion.nombre_institucion if obj.id_institucion else None

    def get_sede_nombre(self, obj):
        return obj.id_sede.nombre_sede if obj.id_sede else None

    def get_instituciones_supervisor(self, obj):
        return instituciones_asignadas_del_supervisor(obj)

    def validate_nombre(self, value):
        val = (value or '').strip()
        if len(val) < 2:
            raise serializers.ValidationError('El nombre debe tener al menos 2 caracteres.')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\.\-]+$', val):
            raise serializers.ValidationError('El nombre contiene caracteres inválidos. Solo se permiten letras y espacios.')
        return val

    def validate_apellido(self, value):
        val = (value or '').strip()
        if len(val) < 2:
            raise serializers.ValidationError('El apellido debe tener al menos 2 caracteres.')
        if not re.match(r'^[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ\s\.\-]+$', val):
            raise serializers.ValidationError('El apellido contiene caracteres inválidos. Solo se permiten letras y espacios.')
        return val

    def validate(self, attrs):
        # Criterio 5: Restricción estricta de campos protegidos
        for campo in self.CAMPOS_PROTEGIDOS:
            attrs.pop(campo, None)
        return attrs


class UsuarioSerializer(serializers.ModelSerializer):
    nombre_completo = serializers.CharField(read_only=True)
    rol_detalle = RolSerializer(source='rol', read_only=True)
    institucion_nombre = serializers.CharField(
        source='id_institucion.nombre_institucion',
        read_only=True
    )
    sede_nombre = serializers.CharField(
        source='id_sede.nombre_sede',
        read_only=True
    )
    instituciones_supervisor = serializers.SerializerMethodField()
    instituciones_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="Lista de IDs de instituciones activas para asignar a un Supervisor."
    )
    estado = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        help_text="Permite indicar 'Activo' o 'Inactivo' como alias de is_active."
    )
    estado_display = serializers.SerializerMethodField()
    esta_bloqueado = serializers.SerializerMethodField()
    creado_por_nombre = serializers.SerializerMethodField()
    creado_en = serializers.DateTimeField(source='fecha_creacion', read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id_usuario',
            'nombre',
            'apellido',
            'nombre_completo',
            'correo',
            'tipo_documento',
            'numero_documento',
            'rol',
            'rol_detalle',
            'id_institucion',
            'institucion_nombre',
            'id_sede',
            'sede_nombre',
            'instituciones_supervisor',
            'instituciones_ids',
            'password',
            'is_active',
            'estado',
            'estado_display',
            'esta_bloqueado',
            'is_staff',
            'debe_cambiar_password',
            'creado_por',
            'creado_por_nombre',
            'fecha_creacion',
            'creado_en',
        ]
        read_only_fields = [
            'id_usuario',
            'nombre_completo',
            'estado_display',
            'esta_bloqueado',
            'creado_por',
            'creado_por_nombre',
            'fecha_creacion',
            'creado_en',
        ]
        extra_kwargs = {
            'nombre': {
                'error_messages': {
                    'required': 'El nombre es obligatorio.',
                    'blank': 'El nombre no puede estar vacío.',
                }
            },
            'apellido': {
                'error_messages': {
                    'required': 'El apellido es obligatorio.',
                    'blank': 'El apellido no puede estar vacío.',
                }
            },
            'correo': {
                'validators': [],
                'error_messages': {
                    'required': 'El correo electrónico es obligatorio.',
                    'blank': 'El correo electrónico no puede estar vacío.',
                    'invalid': 'Ingresa un correo electrónico con formato válido.',
                }
            },
            'tipo_documento': {
                'error_messages': {
                    'required': 'El tipo de documento es obligatorio.',
                    'blank': 'El tipo de documento no puede estar vacío.',
                }
            },
            'numero_documento': {
                'validators': [],
                'error_messages': {
                    'required': 'El número de documento es obligatorio.',
                    'blank': 'El número de documento no puede estar vacío.',
                }
            },
            'password': {
                'write_only': True,
                'required': False,
                'allow_blank': True,
            }
        }

    def get_instituciones_supervisor(self, obj):
        return instituciones_asignadas_del_supervisor(obj)

    def get_esta_bloqueado(self, obj):
        return bool(obj.bloqueado_hasta and obj.bloqueado_hasta > timezone.now())

    def get_estado_display(self, obj):
        if not obj.is_active:
            return 'Inactivo'
        if obj.bloqueado_hasta and obj.bloqueado_hasta > timezone.now():
            return 'Bloqueado'
        return 'Activo'

    def get_creado_por_nombre(self, obj):
        if obj.creado_por_id and obj.creado_por:
            return obj.creado_por.nombre_completo or obj.creado_por.correo
        return None

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Criterio 9: Garantizar que jamás se expongan hashes de contraseñas, tokens ni datos sensibles
        for campo_sensible in (
            'password',
            'codigo_hash',
            'password_reset_code',
            'access',
            'refresh',
            'token',
            'intentos_fallidos_login',
            'bloqueado_hasta',
            'ultimo_intento_fallido',
            'user_permissions',
            'groups',
        ):
            data.pop(campo_sensible, None)
        return data

    def validate_nombre(self, value):
        valor = (value or '').strip()
        if not valor:
            raise serializers.ValidationError('El nombre es obligatorio.')
        return valor

    def validate_apellido(self, value):
        valor = (value or '').strip()
        if not valor:
            raise serializers.ValidationError('El apellido es obligatorio.')
        return valor

    def validate_tipo_documento(self, value):
        valor = (value or '').strip().upper()
        if not valor:
            raise serializers.ValidationError('El tipo de documento es obligatorio.')
        return valor

    def validate_correo(self, value):
        correo = (value or '').strip().lower()
        if not correo:
            raise serializers.ValidationError('El correo electrónico es obligatorio.')
        try:
            validate_email(correo)
        except DjangoValidationError:
            raise serializers.ValidationError('Ingresa un correo electrónico con formato válido.')

        qs = Usuario.objects.filter(correo__iexact=correo)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'Ya existe un usuario registrado con este correo electrónico.'
            )
        return correo

    def validate_numero_documento(self, value):
        numero = (value or '').strip()
        if not numero:
            raise serializers.ValidationError('El número de documento es obligatorio.')
        qs = Usuario.objects.filter(numero_documento__iexact=numero)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'Ya existe un usuario registrado con este número de documento.'
            )
        return numero

    def validate(self, attrs):
        request = self.context.get('request')
        current_user = (
            request.user
            if request and getattr(request, 'user', None) and request.user.is_authenticated
            else None
        )

        # Mapear alias 'estado' -> 'is_active' si fue provisto
        estado_raw = attrs.pop('estado', None)
        if estado_raw is not None and 'is_active' not in attrs:
            estado_norm = str(estado_raw).strip().lower()
            if estado_norm in {'activo', 'activa', 'active', 'true', '1', 'yes', 'si', 'sí'}:
                attrs['is_active'] = True
            elif estado_norm in {'inactivo', 'inactiva', 'inactive', 'false', '0', 'no'}:
                attrs['is_active'] = False

        rol = attrs.get('rol') if 'rol' in attrs else (
            self.instance.rol if self.instance else None
        )

        if not self.instance and not rol:
            raise serializers.ValidationError({
                'rol': 'El rol del usuario es obligatorio.'
            })

        rol_nombre = _normalizar_texto_rol(
            rol.nombre if rol and hasattr(rol, 'nombre') else ''
        )

        # Nadie puede crear ni promover a un Super Administrador mediante la API.
        if _es_rol_superadmin(rol_nombre):
            if not self.instance or not self.instance.es_super_administrador():
                raise serializers.ValidationError({
                    'rol': (
                        'No está permitido registrar ni asignar nuevos usuarios '
                        'con el rol de Super Administrador.'
                    )
                })

        # Protección del Super Administrador existente.
        if self.instance and (self.instance.es_super_administrador() or self.instance.is_superuser):
            if 'is_active' in attrs and not attrs['is_active']:
                raise serializers.ValidationError({
                    'is_active': 'No está permitido desactivar la cuenta del Super Administrador.'
                })
            if not current_user or (
                current_user.id_usuario != self.instance.id_usuario
                and not current_user.is_superuser
            ):
                raise serializers.ValidationError(
                    'No tienes permisos para modificar los datos '
                    'del Super Administrador.'
                )

        # Criterio 10: Restricción de Autogestión de Estado
        # Impedir que cualquier usuario pueda desactivarse o reactivarse a sí mismo.
        if self.instance and current_user and current_user.id_usuario == self.instance.id_usuario:
            if 'is_active' in attrs and bool(attrs['is_active']) != bool(self.instance.is_active):
                raise serializers.ValidationError({
                    'is_active': (
                        'No tienes autorización para activar o desactivar tu propia cuenta.'
                    )
                })

        # Jerarquía de roles y control de alcance institucional al crear o editar usuarios.
        cambio_rol = 'rol' in attrs and (
            not self.instance or self.instance.rol_id != (rol.id_rol if rol else None)
        )
        if current_user:
            es_mismo_usuario = (
                self.instance is not None
                and current_user.id_usuario == self.instance.id_usuario
            )

            # Control de alcance estricto para el Administrador institucional (Criterio 6):
            # Jamás puede asignarse ni asignar a otros otra institución, ni asignar instituciones de supervisor,
            # ni modificar su propio rol ni promover/degradar usuarios fuera de roles de cocina de su institución.
            if current_user.es_administrador() and not (current_user.es_super_administrador() or current_user.is_superuser):
                if 'instituciones_ids' in attrs and attrs.get('instituciones_ids'):
                    raise serializers.ValidationError({
                        'instituciones_ids': (
                            'El Administrador institucional no tiene autorización para asignar múltiples instituciones.'
                        )
                    })

                if 'id_institucion' in attrs:
                    inst_solicitada = attrs.get('id_institucion')
                    inst_solicitada_id = getattr(inst_solicitada, 'id_institucion', inst_solicitada)
                    if inst_solicitada_id != current_user.id_institucion_id:
                        raise serializers.ValidationError({
                            'id_institucion': (
                                'No tienes autorización para asignar o transferir usuarios a otra institución fuera de tu ámbito.'
                            )
                        })

                if 'id_sede' in attrs and attrs.get('id_sede') is not None:
                    sede_solicitada = attrs.get('id_sede')
                    if sede_solicitada.id_institucion_id != current_user.id_institucion_id:
                        raise serializers.ValidationError({
                            'id_sede': (
                                'No tienes autorización para asignar una sede que no pertenece a tu institución.'
                            )
                        })

                if self.instance and self.instance.id_institucion_id != current_user.id_institucion_id:
                    raise serializers.ValidationError({
                        'id_institucion': (
                            'No tienes autorización para modificar usuarios pertenecientes a otra institución.'
                        )
                    })

                if es_mismo_usuario and cambio_rol:
                    raise serializers.ValidationError({
                        'rol': 'No tienes autorización para modificar tu propio rol en el sistema.'
                    })

                if not es_mismo_usuario:
                    if not _es_rol_cocina(rol_nombre):
                        raise serializers.ValidationError({
                            'rol': (
                                'El Administrador institucional solo puede asignar o gestionar roles '
                                'de cocina (Manipuladora Jefe o Manipuladoras).'
                            )
                        })
                    if current_user.id_institucion_id:
                        attrs['id_institucion'] = current_user.id_institucion

            elif not self.instance or cambio_rol:
                if not es_mismo_usuario:
                    if current_user.es_super_administrador() or current_user.is_superuser:
                        es_rol_permitido = (
                            _es_rol_admin_institucional(rol_nombre)
                            or _es_rol_supervisor(rol_nombre)
                        )
                        if not es_rol_permitido:
                            raise serializers.ValidationError({
                                'rol': (
                                    'El Super Administrador solo puede gestionar '
                                    'usuarios con rol de Administrador institucional o Supervisor.'
                                )
                            })
                    else:
                        raise serializers.ValidationError(
                            'Tu rol no tiene autorización para registrar o cambiar roles de usuarios.'
                        )

        es_admin = _es_rol_admin_institucional(rol_nombre)
        es_supervisor = _es_rol_supervisor(rol_nombre)

        # Procesar lista de instituciones_ids (si se envía en el payload)
        instituciones_ids = attrs.get('instituciones_ids', None)
        if instituciones_ids is not None:
            ids_limpios = []
            for raw_id in instituciones_ids:
                if raw_id is not None and int(raw_id) not in ids_limpios:
                    ids_limpios.append(int(raw_id))
            attrs['instituciones_ids'] = ids_limpios

            if es_admin:
                if len(ids_limpios) > 1:
                    raise serializers.ValidationError({
                        'instituciones_ids': (
                            'Un Administrador institucional corresponde a una (1) sola institución. '
                            'No se permite asignarle múltiples instituciones.'
                        )
                    })
                if len(ids_limpios) == 1 and not attrs.get('id_institucion'):
                    inst_unica = Institucion.objects.filter(pk=ids_limpios[0]).first()
                    if not inst_unica:
                        raise serializers.ValidationError({
                            'id_institucion': 'La institución seleccionada no existe.'
                        })
                    attrs['id_institucion'] = inst_unica

            elif es_supervisor:
                instituciones_objs = list(Institucion.objects.filter(pk__in=ids_limpios))
                encontrados_ids = {i.id_institucion for i in instituciones_objs}
                faltantes = [i for i in ids_limpios if i not in encontrados_ids]
                if faltantes:
                    raise serializers.ValidationError({
                        'instituciones_ids': (
                            f"Las siguientes instituciones no existen: {faltantes}."
                        )
                    })
                for inst_obj in instituciones_objs:
                    if not inst_obj.es_activa():
                        raise serializers.ValidationError({
                            'instituciones_ids': (
                                f"No se puede asignar la institución '{inst_obj.nombre_institucion}' "
                                "porque se encuentra en estado inactivo."
                            )
                        })
                    filtro_sup = SupervisorInstitucion.objects.filter(id_institucion=inst_obj)
                    if self.instance:
                        filtro_sup = filtro_sup.exclude(id_supervisor=self.instance)
                    rel_ocupada = filtro_sup.select_related('id_supervisor').first()
                    if rel_ocupada and rel_ocupada.id_supervisor and rel_ocupada.id_supervisor.is_active:
                        raise serializers.ValidationError({
                            'instituciones_ids': (
                                f"La institución '{inst_obj.nombre_institucion}' ya está asignada al "
                                f"Supervisor '{rel_ocupada.id_supervisor.nombre_completo}'."
                            )
                        })

        id_inst = attrs.get('id_institucion') if 'id_institucion' in attrs else (
            self.instance.id_institucion if self.instance else None
        )
        id_sede = attrs.get('id_sede') if 'id_sede' in attrs else (
            self.instance.id_sede if self.instance else None
        )

        is_active_final = attrs.get(
            'is_active',
            self.instance.is_active if self.instance else True
        )
        validando_asignacion_inst = (
            not self.instance
            or 'id_institucion' in attrs
            or 'id_sede' in attrs
            or bool(is_active_final)
        )

        # Criterios 7 y 9: Impedir asignaciones o activación en instituciones o sedes inactivas
        if id_inst and validando_asignacion_inst and not id_inst.es_activa():
            raise serializers.ValidationError({
                'id_institucion': (
                    f"No se puede asignar el usuario a la institución '{id_inst.nombre_institucion}' "
                    "porque se encuentra en estado inactivo."
                )
            })

        if id_sede:
            if validando_asignacion_inst and not id_sede.es_activa():
                raise serializers.ValidationError({
                    'id_sede': (
                        f"No se puede asignar el usuario a la sede '{id_sede.nombre_sede}' "
                        "porque se encuentra en estado inactivo."
                    )
                })
            if id_inst and id_sede.id_institucion_id != id_inst.id_institucion:
                raise serializers.ValidationError({
                    'id_sede': 'La sede seleccionada no pertenece a la institución asignada.'
                })

        # Criterio 8: Un Administrador institucional corresponde a 1 sola institución
        if es_admin and not id_inst:
            # Si existen instituciones en el catálogo o si la petición proviene de un SuperAdmin/API,
            # exigir la institución obligatoria para el Administrador institucional.
            if current_user is not None or Institucion.objects.exists():
                raise serializers.ValidationError({
                    'id_institucion': (
                        'El Administrador institucional debe tener asignada una (1) institución activa.'
                    )
                })

        # Criterio 10: Unicidad del Administrador institucional activo por institución

        if es_admin and id_inst and is_active_final:
            filtro_admin = Usuario.objects.filter(
                id_institucion=id_inst,
                is_active=True
            ).filter(
                Q(rol__nombre__iexact='Administrador')
                | Q(rol__nombre__iexact='administrador')
                | Q(rol__nombre__iexact='admin')
                | Q(rol__nombre__iexact='Administrador Institucional')
                | (Q(rol__nombre__icontains='admin') & ~Q(rol__nombre__icontains='super'))
            )

            if self.instance:
                filtro_admin = filtro_admin.exclude(
                    pk=self.instance.pk
                )

            admin_existente = filtro_admin.first()

            if admin_existente:
                inst_nom = getattr(
                    id_inst,
                    'nombre_institucion',
                    'esta institución'
                )

                raise serializers.ValidationError({
                    'id_institucion': (
                        f"La institución '{inst_nom}' ya tiene asignado "
                        f"al Administrador '{admin_existente.nombre_completo}'. "
                        "Cada institución solo puede tener un único "
                        "Administrador activo."
                    )
                })

        return attrs

    def _obtener_ip_request(self):
        request = self.context.get('request')
        if not request or not hasattr(request, 'META'):
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _sincronizar_instituciones_supervisor(self, usuario, instituciones_ids):
        if instituciones_ids is None:
            return
        if not usuario.es_supervisor():
            return
        SupervisorInstitucion.objects.filter(
            id_supervisor=usuario
        ).exclude(
            id_institucion_id__in=instituciones_ids
        ).delete()
        existentes = set(
            SupervisorInstitucion.objects.filter(
                id_supervisor=usuario
            ).values_list('id_institucion_id', flat=True)
        )
        for inst_id in instituciones_ids:
            if inst_id not in existentes:
                SupervisorInstitucion.objects.create(
                    id_supervisor=usuario,
                    id_institucion_id=inst_id
                )

    @transaction.atomic
    def create(self, validated_data):
        instituciones_ids = validated_data.pop('instituciones_ids', None)
        password = validated_data.pop('password', None)

        request = self.context.get('request')
        actor = (
            request.user
            if request and getattr(request, 'user', None) and request.user.is_authenticated
            else None
        )

        # Criterio 11 y 12: Si no se provee contraseña, generar una clave temporal segura
        # y marcar debe_cambiar_password=True; jamás almacenar texto plano.
        password_fue_temporal = False
        if not password or not str(password).strip():
            password = generar_password_temporal_segura()
            validated_data.setdefault('debe_cambiar_password', True)
            password_fue_temporal = True
        else:
            password = str(password).strip()

        if actor and 'creado_por' not in validated_data:
            validated_data['creado_por'] = actor

        usuario = Usuario(**validated_data)
        usuario.set_password(password)
        usuario.save()

        if instituciones_ids is not None:
            self._sincronizar_instituciones_supervisor(usuario, instituciones_ids)

        # Criterio 15: Registrar en auditoría quién creó la cuenta y el timestamp exacto
        rol_txt = usuario.rol.nombre if usuario.rol else 'Sin rol'
        inst_txt = (
            usuario.id_institucion.nombre_institucion
            if usuario.id_institucion
            else (f"Instituciones supervisor: {instituciones_ids}" if instituciones_ids else 'Sin institución')
        )
        estado_inicial = 'Activo' if usuario.is_active else 'Inactivo'
        AuditoriaUsuario.objects.create(
            usuario_afectado=usuario,
            usuario_actor=actor,
            accion='CREACION',
            estado_anterior='',
            estado_nuevo=estado_inicial,
            detalle=(
                f"Creación de usuario '{usuario.correo}' con rol '{rol_txt}', "
                f"estado '{estado_inicial}', "
                f"asignación '{inst_txt}'."
            ),
            ip_address=self._obtener_ip_request(),
        )

        # Disparar envío de enlace seguro de activación/configuración de contraseña
        if password_fue_temporal or usuario.debe_cambiar_password:
            enviar_correo_activacion_cuenta(usuario)

        return usuario

    @transaction.atomic
    def update(self, instance, validated_data):
        instituciones_ids = validated_data.pop('instituciones_ids', None)
        password = validated_data.pop('password', None)

        prev_is_active = bool(instance.is_active)
        estado_anterior_str = 'Activo' if prev_is_active else 'Inactivo'

        instance = super().update(instance, validated_data)

        if password and str(password).strip():
            instance.set_password(str(password).strip())
            instance.save(update_fields=['password'])

        if instituciones_ids is not None:
            self._sincronizar_instituciones_supervisor(instance, instituciones_ids)

        # Si el usuario no es Supervisor (p. ej. pasó a ser Administrador institucional), limpiar relaciones múltiples de supervisor
        if not instance.es_supervisor():
            SupervisorInstitucion.objects.filter(id_supervisor=instance).delete()
        elif instance.id_institucion_id is not None or instance.id_sede_id is not None:
            # Si el usuario es Supervisor, limpiar institución/sede directa residual
            instance.id_institucion = None
            instance.id_sede = None
            instance.save(update_fields=['id_institucion', 'id_sede'])

        new_is_active = bool(instance.is_active)
        estado_nuevo_str = 'Activo' if new_is_active else 'Inactivo'
        cambio_estado = prev_is_active != new_is_active

        # Criterio 5: Invalidar y revocar sesiones activas de inmediato al desactivar una cuenta
        if not new_is_active:
            revocar_sesiones_activas_usuario(instance)
        elif cambio_estado and new_is_active:
            if instance.intentos_fallidos_login > 0 or instance.bloqueado_hasta is not None:
                instance.intentos_fallidos_login = 0
                instance.bloqueado_hasta = None
                instance.save(update_fields=['intentos_fallidos_login', 'bloqueado_hasta'])

        request = self.context.get('request')
        actor = (
            request.user
            if request and getattr(request, 'user', None) and request.user.is_authenticated
            else None
        )
        ip_cliente = self._obtener_ip_request()

        # Criterio 9: Auditoría y Trazabilidad del cambio de estado (usuario actor, timestamp, estado anterior y nuevo)
        if cambio_estado:
            accion_estado = 'ACTIVACION' if new_is_active else 'DESACTIVACION'
            AuditoriaUsuario.objects.create(
                usuario_afectado=instance,
                usuario_actor=actor,
                accion=accion_estado,
                estado_anterior=estado_anterior_str,
                estado_nuevo=estado_nuevo_str,
                detalle=(
                    f"{'Activación' if new_is_active else 'Desactivación'} de cuenta de usuario '{instance.correo}': "
                    f"estado anterior '{estado_anterior_str}', estado nuevo '{estado_nuevo_str}'."
                ),
                ip_address=ip_cliente,
            )

        otros_campos = {k for k in validated_data.keys() if k != 'is_active'}
        if not cambio_estado or otros_campos or instituciones_ids is not None or password:
            AuditoriaUsuario.objects.create(
                usuario_afectado=instance,
                usuario_actor=actor,
                accion='ACTUALIZACION',
                estado_anterior=estado_anterior_str,
                estado_nuevo=estado_nuevo_str,
                detalle=(
                    f"Actualización de usuario '{instance.correo}' "
                    f"(estado anterior: '{estado_anterior_str}', estado nuevo: '{estado_nuevo_str}')."
                ),
                ip_address=ip_cliente,
            )

        return instance


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    username_field = 'correo'

    MENSAJE_CREDENCIALES_INVALIDAS = (
        'Correo electrónico o contraseña incorrectos. '
        'Verifica tus datos e inténtalo nuevamente.'
    )
    MENSAJE_CUENTA_BLOQUEADA = (
        'La cuenta ha sido bloqueada temporalmente por múltiples intentos '
        'fallidos de inicio de sesión. Por favor intenta nuevamente más tarde.'
    )
    MENSAJE_CUENTA_INACTIVA = (
        'Tu cuenta se encuentra inactiva o sin autorización vigente. '
        'Contacta al administrador del sistema.'
    )

    @staticmethod
    def _rol_para_cliente(user):
        if user.is_superuser:
            return 'Super Administrador'

        return user.rol.nombre if user.rol else None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['correo'] = serializers.EmailField(
            required=True,
            error_messages={
                'required': 'El correo electrónico es obligatorio.',
                'blank': 'El correo electrónico es obligatorio.',
                'invalid': 'Ingresa un correo electrónico con formato válido.',
            }
        )
        self.fields['password'] = serializers.CharField(
            required=True,
            write_only=True,
            error_messages={
                'required': 'La contraseña es obligatoria.',
                'blank': 'La contraseña es obligatoria.',
            }
        )

        if 'username' in self.fields:
            del self.fields['username']

    def _obtener_ip_cliente(self):
        request = self.context.get('request')
        if not request:
            return None
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')

    def _registrar_intento(self, correo, usuario=None, exitoso=False, motivo=''):
        IntentoAutenticacion.objects.create(
            correo=correo,
            usuario=usuario,
            exitoso=exitoso,
            ip_address=self._obtener_ip_cliente(),
            motivo=motivo,
        )

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        token['id_usuario'] = user.id_usuario
        token['correo'] = user.correo
        token['nombre'] = user.nombre
        token['rol'] = cls._rol_para_cliente(user)
        token['is_superuser'] = bool(user.is_superuser)
        token['debe_cambiar_password'] = bool(
            getattr(user, 'debe_cambiar_password', False)
        )
        token['id_institucion'] = user.id_institucion_id
        token['institucion'] = (
            user.id_institucion.nombre_institucion
            if user.id_institucion else None
        )
        token['id_sede'] = user.id_sede_id

        return token

    def validate(self, attrs):
        correo = attrs.get('correo', '').strip().lower()
        password = attrs.get('password')

        ahora = timezone.now()
        max_intentos = max(1, int(getattr(settings, 'LOGIN_MAX_FAILED_ATTEMPTS', 5)))
        minutos_bloqueo = max(1, int(getattr(settings, 'LOGIN_LOCKOUT_DURATION_MINUTES', 15)))
        duracion_bloqueo = timedelta(minutes=minutos_bloqueo)

        lock_cache_key = f"login_lockout:{correo}"
        fail_cache_key = f"login_fails:{correo}"

        try:
            usuario = Usuario.objects.select_related(
                'rol',
                'id_institucion',
                'id_sede'
            ).get(correo__iexact=correo)
        except Usuario.DoesNotExist:
            bloqueado_cache = cache.get(lock_cache_key)
            if bloqueado_cache and bloqueado_cache > ahora:
                self._registrar_intento(correo, None, False, 'cuenta_bloqueada')
                raise AuthenticationFailed(
                    self.MENSAJE_CUENTA_BLOQUEADA,
                    code='account_locked',
                )

            intentos_previos = int(cache.get(fail_cache_key, 0)) + 1
            self._registrar_intento(correo, None, False, 'credenciales_invalidas')

            if intentos_previos >= max_intentos:
                cache.set(lock_cache_key, ahora + duracion_bloqueo, timeout=minutos_bloqueo * 60)
                cache.delete(fail_cache_key)
                raise AuthenticationFailed(
                    self.MENSAJE_CUENTA_BLOQUEADA,
                    code='account_locked',
                )

            cache.set(fail_cache_key, intentos_previos, timeout=minutos_bloqueo * 60)
            raise AuthenticationFailed(
                self.MENSAJE_CREDENCIALES_INVALIDAS,
                code='invalid_credentials',
            )

        # Verificar si la cuenta tiene un bloqueo temporal activo
        if usuario.bloqueado_hasta:
            if usuario.bloqueado_hasta > ahora:
                self._registrar_intento(correo, usuario, False, 'cuenta_bloqueada')
                raise AuthenticationFailed(
                    self.MENSAJE_CUENTA_BLOQUEADA,
                    code='account_locked',
                )
            else:
                # El bloqueo temporal ya expiró; se restablece el contador
                usuario.intentos_fallidos_login = 0
                usuario.bloqueado_hasta = None
                usuario.save(update_fields=['intentos_fallidos_login', 'bloqueado_hasta'])

        if not check_password(password, usuario.password):
            usuario.intentos_fallidos_login = (usuario.intentos_fallidos_login or 0) + 1
            usuario.ultimo_intento_fallido = ahora

            if usuario.intentos_fallidos_login >= max_intentos:
                usuario.bloqueado_hasta = ahora + duracion_bloqueo
                usuario.save(update_fields=[
                    'intentos_fallidos_login',
                    'ultimo_intento_fallido',
                    'bloqueado_hasta',
                ])
                self._registrar_intento(correo, usuario, False, 'bloqueo_por_intentos')
                raise AuthenticationFailed(
                    self.MENSAJE_CUENTA_BLOQUEADA,
                    code='account_locked',
                )

            usuario.save(update_fields=['intentos_fallidos_login', 'ultimo_intento_fallido'])
            self._registrar_intento(correo, usuario, False, 'credenciales_invalidas')
            raise AuthenticationFailed(
                self.MENSAJE_CREDENCIALES_INVALIDAS,
                code='invalid_credentials',
            )

        if not usuario.is_active:
            self._registrar_intento(correo, usuario, False, 'usuario_inactivo')
            raise AuthenticationFailed(
                self.MENSAJE_CUENTA_INACTIVA,
                code='user_inactive',
            )

        rol_cliente = self._rol_para_cliente(usuario)
        if not rol_cliente:
            self._registrar_intento(correo, usuario, False, 'sin_autorizacion_vigente')
            raise AuthenticationFailed(
                self.MENSAJE_CUENTA_INACTIVA,
                code='unauthorized_user',
            )

        # Autenticación exitosa: limpiar intentos fallidos y bloqueo previo
        if usuario.intentos_fallidos_login > 0 or usuario.bloqueado_hasta is not None:
            usuario.intentos_fallidos_login = 0
            usuario.bloqueado_hasta = None
            usuario.save(update_fields=['intentos_fallidos_login', 'bloqueado_hasta'])

        cache.delete(fail_cache_key)
        cache.delete(lock_cache_key)
        self._registrar_intento(correo, usuario, True, 'login_exitoso')

        refresh = self.get_token(usuario)
        access_token_obj = refresh.access_token
        registrar_token_emitido(refresh, usuario)
        registrar_token_emitido(access_token_obj, usuario)

        inst_nombre = (
            usuario.id_institucion.nombre_institucion
            if usuario.id_institucion else None
        )

        sede_nombre = (
            usuario.id_sede.nombre_sede
            if usuario.id_sede else None
        )

        instituciones_sup = instituciones_asignadas_del_supervisor(
            usuario
        )

        if not inst_nombre and instituciones_sup:
            inst_nombre = instituciones_sup[0]['nombre_institucion']

        return {
            'access': str(access_token_obj),
            'refresh': str(refresh),
            'usuario': {
                'id_usuario': usuario.id_usuario,
                'nombre': usuario.nombre,
                'apellido': usuario.apellido,
                'correo': usuario.correo,
                'numero_documento': usuario.numero_documento,
                'rol': rol_cliente,
                'estado': 'Activo' if usuario.is_active else 'Inactivo',
                'is_active': bool(usuario.is_active),
                'id_institucion': usuario.id_institucion_id,
                'institucion': inst_nombre,
                'institucion_nombre': inst_nombre,
                'id_sede': usuario.id_sede_id,
                'sede_nombre': sede_nombre,
                'instituciones_supervisor': instituciones_sup,
                'is_superuser': bool(usuario.is_superuser),
                'debe_cambiar_password': bool(
                    getattr(usuario, 'debe_cambiar_password', False)
                ),
            }
        }


class CustomTokenRefreshSerializer(TokenRefreshSerializer):
    """
    Valida que el usuario propietario del RefreshToken continúe activo
    y registra el nuevo AccessToken emitido en OutstandingToken.
    """

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        jti = refresh.get("jti")
        if jti and (
            cache.get(f"revoked_jti:{jti}")
            or BlacklistedToken.objects.filter(token__jti=jti).exists()
        ):
            raise AuthenticationFailed(
                "El token de refresco ha sido revocado o la sesión fue invalidada.",
                code="token_not_valid",
            )

        user_id = refresh.get("user_id") or refresh.get("id_usuario")
        usuario = Usuario.objects.filter(id_usuario=user_id).first() if user_id else None
        if not usuario or not usuario.is_active:
            raise AuthenticationFailed(
                CustomTokenObtainPairSerializer.MENSAJE_CUENTA_INACTIVA,
                code="user_inactive",
            )

        data = super().validate(attrs)
        if "access" in data:
            try:
                registrar_token_emitido(AccessToken(data["access"]), usuario)
            except Exception:
                pass
        return data
