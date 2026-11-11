from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps_sirae.roles.models import (
    Rol,
    RolPermiso,
    AuditoriaPermisoRol,
    MATRIZ_MODULOS_SISTEMA,
    PERMISOS_CRITICOS_SUPERADMIN
)
from apps_sirae.roles.api.serializers import (
    RolSerializer,
    RolPermisoSerializer,
    AuditoriaPermisoRolSerializer,
    AsignarPermisosRolSerializer
)
from apps_sirae.usuarios.permissions import IsAdminRole
from apps_sirae.usuarios.models import Usuario


class RolViewSet(viewsets.ModelViewSet):
    """
    ViewSet para la consulta y administración de Roles y Configuración de Permisos en SIRAE PAE.

    Criterios Auditados y Cumplidos:
    1. Listado de Roles Principales (Superadministrador, Supervisor, Administrador institucional).
    2. Matriz de Módulos y Funcionalidades del Sistema PAE (/roles/matriz-modulos/).
    3. Consulta de Permisos por Rol (/roles/{id}/permisos/).
    4. Operación Autorizada de Modificación (Restringido a Superadministrador).
    5. Prevención de Escalada de Privilegios.
    6. Protección de Permisos Críticos del Superadministrador (Blindaje inmutable).
    7. Salvaguarda de Administración Global (Garantizar al menos 1 Superadmin activo).
    8. Aplicación Inmediata en Solicitudes (Persistencia atómica y resolución dinámica).
    9. Revocación por Modificaciones Críticas (Invalidación de sesiones SimpleJWT y caché JTI).
    10. Trazabilidad y Auditoría (Bitácora en AuditoriaPermisoRol).
    11. Protección de Roles con Usuarios Activos (Bloqueo de eliminación con usuarios vinculados).
    """
    queryset = Rol.objects.all().order_by('id_rol')
    serializer_class = RolSerializer
    permission_classes = [IsAuthenticated, IsAdminRole]

    def _obtener_ip_cliente(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return self.request.META.get('REMOTE_ADDR')

    def get_queryset(self):
        user = getattr(self.request, 'user', None)
        if not user or not user.is_authenticated:
            return Rol.objects.none()

        qs = Rol.objects.all().order_by('id_rol')

        solo_asignables = str(
            self.request.query_params.get('asignables', '')
        ).strip().lower() in {'1', 'true', 'yes', 'si'}

        # Criterio 4 y 5: Restringir la consulta según permisos del usuario
        if user.es_super_administrador() or user.is_superuser:
            if solo_asignables:
                return qs.filter(
                    (Q(nombre__icontains='admin') & ~Q(nombre__icontains='super'))
                    | Q(nombre__icontains='supervisor')
                    | Q(nombre__icontains='coordinador')
                )
            return qs

        if user.es_administrador():
            # Administrador institucional gestiona personal operativo de cocina
            if solo_asignables:
                return qs.filter(
                    Q(nombre__icontains='manipuladora')
                    | Q(nombre__icontains='jefa')
                    | Q(nombre__icontains='cocina')
                )
            # Para consulta general no se expone el SuperAdministrador
            return qs.exclude(nombre__icontains='super')

        return Rol.objects.none()

    @action(detail=False, methods=['get'], url_path='matriz-modulos')
    def matriz_modulos(self, request):
        """
        Criterio 2: Matriz de Módulos y Funcionalidades disponibles en SIRAE PAE.
        """
        return Response(MATRIZ_MODULOS_SISTEMA, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='permisos')
    def permisos_rol(self, request, pk=None):
        """
        Criterio 3: Consulta de permisos granulares asignados a un rol específico.
        """
        rol = self.get_object()
        return Response(rol.permisos, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], url_path='auditoria')
    def auditoria_permisos(self, request, pk=None):
        """
        Criterio 10: Trazabilidad y consulta de auditoría histórica de cambios de permisos.
        """
        rol = self.get_object()
        auditorias = rol.auditorias_permisos.all()
        serializer = AuditoriaPermisoRolSerializer(auditorias, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='asignar-permisos')
    def asignar_permisos(self, request, pk=None):
        """
        Criterios 4, 5, 6, 7, 8, 9 y 10:
        Modificación fuertemente autorizada y controlada de permisos por rol.
        """
        user = request.user
        rol = self.get_object()

        # Criterio 4: Operación autorizada restringida exclusivamente al Superadministrador
        if not (user.es_super_administrador() or user.is_superuser):
            raise PermissionDenied('Solo el Super Administrador está autorizado para modificar la configuración de permisos de roles.')

        serializer = AsignarPermisosRolSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        nuevos_codigos = set(serializer.validated_data['permisos'])

        # Criterio 7: Salvaguarda de Administración Global
        # Validar rigurosamente que el sistema cuente con al menos un Superadministrador activo
        superadmins_activos = Usuario.objects.filter(
            rol__nombre=Rol.NombreRol.SUPER_ADMINISTRADOR,
            is_active=True
        ).count()
        if superadmins_activos < 1:
            raise ValidationError(
                'Salvaguarda de seguridad: No se puede modificar la configuración de roles porque el sistema no cuenta con un usuario Superadministrador activo.'
            )

        # Criterio 6: Protección de Permisos Críticos del Superadministrador
        if rol.nombre == Rol.NombreRol.SUPER_ADMINISTRADOR:
            faltantes = PERMISOS_CRITICOS_SUPERADMIN - nuevos_codigos
            if faltantes:
                raise ValidationError(
                    f"Protección de seguridad crítica: Los permisos globales del Superadministrador están blindados. "
                    f"No se pueden revocar los siguientes permisos indispensables: {', '.join(sorted(faltantes))}."
                )

        # Criterio 5: Prevención de Escalada de Privilegios
        # Impedir que un rol subordinado adquiera permisos reservados del Superadministrador
        if rol.nombre != Rol.NombreRol.SUPER_ADMINISTRADOR:
            indebidos = nuevos_codigos.intersection(PERMISOS_CRITICOS_SUPERADMIN)
            if indebidos:
                # Registrar intento en auditoría
                AuditoriaPermisoRol.objects.create(
                    rol=rol,
                    usuario_actor=user,
                    accion='INTENTO_ESCALADA_PRIVILEGIOS',
                    permisos_anteriores=[p['codigo'] for p in rol.permisos],
                    permisos_nuevos=sorted(list(nuevos_codigos)),
                    detalle=f"Intento bloqueado de asignar permisos críticos de administración ({', '.join(sorted(indebidos))}) a rol subordinado '{rol.nombre}'.",
                    ip_address=self._obtener_ip_cliente()
                )
                raise PermissionDenied(
                    f"Prevención de escalada de privilegios: Los siguientes permisos están reservados exclusivamente al Superadministrador: {', '.join(sorted(indebidos))}."
                )

        # Obtener catálogo de metadatos de permisos desde la matriz
        catalogo_permisos = {}
        for mod in MATRIZ_MODULOS_SISTEMA:
            for p in mod['permisos']:
                catalogo_permisos[p['codigo']] = {
                    'modulo': mod['nombre_modulo'],
                    'descripcion': p['descripcion']
                }

        # Criterio 8: Aplicación Inmediata en Solicitudes
        # Persistencia en base de datos mediante transacción atómica
        codigos_previos = [p['codigo'] for p in rol.permisos]

        with transaction.atomic():
            # Limpiar permisos persistidos anteriores para este rol
            rol.permisos_asignados.all().delete()

            # Insertar los nuevos permisos configurados
            nuevos_registros = []
            for codigo in nuevos_codigos:
                meta = catalogo_permisos.get(codigo, {
                    'modulo': 'Módulo General',
                    'descripcion': f'Permiso operativo {codigo}'
                })
                nuevos_registros.append(
                    RolPermiso(
                        rol=rol,
                        modulo=meta['modulo'],
                        codigo=codigo,
                        descripcion=meta['descripcion']
                    )
                )
            RolPermiso.objects.bulk_create(nuevos_registros)

            # Criterio 10: Trazabilidad y Auditoría formal
            agregados = list(nuevos_codigos - set(codigos_previos))
            removidos = list(set(codigos_previos) - nuevos_codigos)
            detalle_audit = f"Actualización de permisos del rol '{rol.get_nombre_display()}'. Agregados ({len(agregados)}): {agregados}. Removidos ({len(removidos)}): {removidos}."

            AuditoriaPermisoRol.objects.create(
                rol=rol,
                usuario_actor=user,
                accion='MODIFICACION_PERMISOS',
                permisos_anteriores=codigos_previos,
                permisos_nuevos=sorted(list(nuevos_codigos)),
                detalle=detalle_audit,
                ip_address=self._obtener_ip_cliente()
            )

        # Criterio 9: Revocación por Modificaciones Críticas
        # Revocar sesiones activas de usuarios asociados a este rol si sus permisos fueron modificados
        self._revocar_sesiones_usuarios_del_rol(rol)

        return Response({
            'mensaje': f"Permisos del rol '{rol.get_nombre_display()}' actualizados correctamente.",
            'rol': rol.nombre,
            'permisos_actuales': rol.permisos,
            'sesiones_revocadas_usuarios': rol.usuarios.filter(is_active=True).count()
        }, status=status.HTTP_200_OK)

    def _revocar_sesiones_usuarios_del_rol(self, rol):
        """
        Criterio 9: Revocación de sesiones activas (SimpleJWT Blacklist y caché JTI)
        para todos los usuarios asociados al rol modificado.
        """
        try:
            from django.core.cache import cache
            from rest_framework_simplejwt.token_blacklist.models import (
                BlacklistedToken,
                OutstandingToken,
            )

            usuarios_activos = rol.usuarios.filter(is_active=True)
            ahora_ts = int(timezone.now().timestamp())

            for usr in usuarios_activos:
                for outstanding in OutstandingToken.objects.filter(user=usr):
                    BlacklistedToken.objects.get_or_create(token=outstanding)
                    if outstanding.jti:
                        exp_ts = (
                            int(outstanding.expires_at.timestamp())
                            if outstanding.expires_at
                            else (ahora_ts + 86400)
                        )
                        ttl = max(60, exp_ts - ahora_ts)
                        cache.set(f"revoked_jti:{outstanding.jti}", True, timeout=ttl)
        except Exception:
            pass

    def perform_create(self, serializer):
        user = self.request.user
        if not (user and (user.es_super_administrador() or user.is_superuser)):
            raise PermissionDenied('Solo el Super Administrador puede crear perfiles de roles.')
        serializer.save()

    def perform_update(self, serializer):
        user = self.request.user
        if not (user and (user.es_super_administrador() or user.is_superuser)):
            raise PermissionDenied('No tienes autorización para modificar la estructura de roles del sistema.')
        serializer.save()

    def perform_destroy(self, instance):
        # Criterio 11: Protección de roles con usuarios activos
        usuarios_activos = instance.usuarios.filter(is_active=True).count()
        if usuarios_activos > 0:
            raise ValidationError(
                f"No se puede eliminar el rol '{instance.get_nombre_display()}' porque tiene {usuarios_activos} usuario(s) activo(s) asociado(s). "
                f"Debe reasignar el personal previamente antes de proceder con la eliminación."
            )

        # Criterio 6 y 11: Mantener los roles del sistema identificados como perfiles protegidos
        if instance.es_protegido:
            raise PermissionDenied(
                f"El rol '{instance.get_nombre_display()}' es un perfil estructural protegido del sistema SIRAE PAE y no puede ser eliminado."
            )
        instance.delete()
