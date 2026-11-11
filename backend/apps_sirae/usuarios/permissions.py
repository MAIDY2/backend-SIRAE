from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminRole(BasePermission):
    """
    Permiso que autoriza únicamente a usuarios con el rol de Administrador o Super Administrador.
    """
    message = "Acceso restringido: Se requiere el rol de Administrador."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_administrador() or request.user.es_super_administrador()


class IsSupervisorRole(BasePermission):
    """
    Permiso que autoriza a usuarios con rol de Supervisor (o Coordinador).
    """
    message = "Acceso restringido: Se requiere el rol de Supervisor."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_supervisor() or request.user.es_super_administrador()


class IsSupervisorOrAdminRole(BasePermission):
    """
    Permite al Supervisor gestionar la operación PAE, al Administrador supervisarla y al Super Administrador auditoría total.
    """
    message = "Acceso restringido: se requiere el rol de Supervisor, Administrador o Super Administrador."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (
            request.user.es_supervisor()
            or request.user.es_administrador()
            or request.user.es_super_administrador()
        )


class IsJefaOrAdminRole(BasePermission):
    """
    Permite a la Jefa gestionar la operación de menús, al Administrador supervisarla/mantenerla
    y al Super Administrador control total.
    """
    message = "Acceso restringido: se requiere el rol de Jefa de manipuladoras, Administrador o Super Administrador."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (
            request.user.es_jefa_manipuladoras()
            or request.user.es_administrador()
            or getattr(request.user, 'es_super_administrador', lambda: False)()
        )


# Alias explícito de compatibilidad
IsJefaOrAdminOrSuperAdminRole = IsJefaOrAdminRole


# Alias para compatibilidad
IsCoordinadorRole = IsSupervisorRole


class IsJefaRole(BasePermission):
    """
    Permiso que autoriza a usuarios con rol de Jefa de Manipuladoras.
    """
    message = "Acceso restringido: Se requiere el rol de Jefa de manipuladoras."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_jefa_manipuladoras()


class IsManipuladoraRole(BasePermission):
    """
    Permiso que autoriza a usuarios con rol de Manipuladora de alimentos.
    """
    message = "Acceso restringido: Se requiere el rol de Manipuladora de alimentos."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_manipuladora()


class IsAdminOrReadOnly(BasePermission):
    """
    Permiso que permite lectura (GET, HEAD, OPTIONS) a cualquier usuario autenticado,
    pero reserva la modificación (POST, PUT, PATCH, DELETE) al Administrador o Super Administrador.
    """
    message = "Solo el Administrador o Super Administrador pueden modificar estos registros."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return (
            request.user.es_administrador()
            or getattr(request.user, 'es_super_administrador', lambda: False)()
        )


# Alias explícito de compatibilidad
IsAdminOrSuperAdminOrReadOnly = IsAdminOrReadOnly


class IsSuperAdminRole(BasePermission):
    """
    Permiso que autoriza únicamente al Super Administrador.
    """
    message = "Acceso restringido: Se requiere el rol de Super Administrador."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return getattr(request.user, 'es_super_administrador', lambda: False)()


class IsSuperAdminOrReadOnly(BasePermission):
    """
    Permite lectura a cualquier usuario autenticado, pero reserva
    la creación/modificación/eliminación exclusivamente al Super Administrador.
    Aplica a catálogo global (productos/ingredientes, categorías, unidades,
    tipos de mercado, porciones y minutas) e instituciones y sedes.
    """
    message = "Solo el Super Administrador puede crear o modificar estos registros."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return getattr(request.user, 'es_super_administrador', lambda: False)()


class IsOperationalAuditedRole(BasePermission):
    """
    Regla de negocio PAE:
    En módulos operativos (asistencia diaria, selección de menús, avance de cocina, entregas),
    el Super Administrador tiene visibilidad total en modo lectura (auditoría),
    pero NO PUEDE realizar operaciones de registro o modificación.
    """
    message = "El Super Administrador solo tiene acceso de consulta y auditoría en este módulo operativo."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if getattr(request.user, 'es_super_administrador', lambda: False)():
            return request.method in SAFE_METHODS
        return True


class IsNotAdminRole(BasePermission):
    """
    Regla de negocio PAE:
    El Administrador y el Super Administrador NO seleccionan el menú diario ni registran asistencia diaria
    (no reemplazan la función operativa de la jefa).
    El Super Administrador puede consultar en modo auditoría (SAFE_METHODS).
    """
    message = "No está autorizado para realizar operaciones exclusivas de la Jefa de manipuladoras."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS and getattr(request.user, 'es_super_administrador', lambda: False)():
            return True
        if request.user.es_administrador() or getattr(request.user, 'es_super_administrador', lambda: False)():
            return False
        return True


class UsuarioConsultationAndScopePermission(BasePermission):
    """
    Criterios 5, 6 y 7 de Consulta y Búsqueda de Usuarios:
    - Criterio 5 (Superadministrador): Puede consultar y visualizar usuarios de todas
      las instituciones del sistema sin restricciones.
    - Criterio 6 (Administrador Institucional): Únicamente puede consultar usuarios
      pertenecientes estrictamente a su propia institución y dentro de las facultades autorizadas.
    - Criterio 7 (Supervisor): Únicamente puede consultar información de otros usuarios
      cuando una funcionalidad específica y explícita se lo permita; fuera de ella, solo su propio perfil.
    """
    message = "No tienes autorización para consultar o gestionar usuarios fuera de tu ámbito institucional."

    FUNCIONALIDADES_SUPERVISION = {
        'supervision_pae',
        'supervision_institucional',
        'instituciones_asignadas',
        'equipo_institucional',
    }

    @classmethod
    def supervisor_tiene_funcionalidad_explicita(cls, request, view) -> bool:
        if getattr(view, 'action', '') == 'consulta_supervision':
            return True
        params = getattr(request, 'query_params', {}) or {}
        funcionalidad = (
            params.get('funcionalidad')
            or params.get('contexto')
            or params.get('ambito')
            or ''
        ).strip().lower()
        return funcionalidad in cls.FUNCIONALIDADES_SUPERVISION

    def has_permission(self, request, view):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False

        # Autogestión de perfil propio: cualquier usuario autenticado y activo puede gestionar su perfil
        if getattr(view, 'action', '') == 'me':
            return bool(user.is_active)

        if request.method in SAFE_METHODS:
            return True

        if getattr(view, 'action', '') in {'create', 'update', 'partial_update', 'destroy', 'cambiar_estado'} or request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            return bool(
                user.es_super_administrador()
                or user.is_superuser
                or user.es_administrador()
            )

        return True

    def has_object_permission(self, request, view, obj):
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return False

        # Autogestión de perfil propio
        if getattr(view, 'action', '') == 'me':
            return bool(user.is_active and obj.id_usuario == user.id_usuario)

        # Criterio 5: El Superadministrador tiene visibilidad total sin restricciones
        if user.es_super_administrador() or user.is_superuser:
            return True

        # Criterio 6: El Administrador institucional solo accede a su propia institución y nunca a SuperAdmin
        if user.es_administrador():
            if obj.es_super_administrador() or obj.is_superuser:
                return False
            if not user.id_institucion_id:
                return obj.id_usuario == user.id_usuario
            return obj.id_institucion_id == user.id_institucion_id

        # Criterio 3 y 10: Usuarios sin privilegios administrativos (Supervisor, Jefa, Manipuladora)
        # jamás pueden ejecutar modificaciones ni autogestionar su propio estado
        if request.method not in SAFE_METHODS:
            return False

        # Criterio 7: El Supervisor solo consulta otros usuarios si la funcionalidad explícita lo habilita
        # y pertenecen a sus instituciones asignadas
        if user.es_supervisor():
            if obj.id_usuario == user.id_usuario:
                return True
            if obj.es_super_administrador() or obj.is_superuser:
                return False
            if not self.supervisor_tiene_funcionalidad_explicita(request, view):
                return False
            obtener_insts = getattr(view, '_obtener_instituciones_asignadas_supervisor', None)
            inst_ids = obtener_insts(user) if callable(obtener_insts) else set()
            return bool(obj.id_institucion_id and obj.id_institucion_id in inst_ids)

        return obj.id_usuario == user.id_usuario

