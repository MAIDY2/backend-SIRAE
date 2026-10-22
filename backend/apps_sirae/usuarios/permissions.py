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
    Permite a la Jefa gestionar la operación de menús y al Administrador mantenerla.
    """
    message = "Acceso restringido: se requiere el rol de Jefa de manipuladoras o Administrador."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_jefa_manipuladoras() or request.user.es_administrador()


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
    pero reserva la modificación (POST, PUT, PATCH, DELETE) exclusivamente al Administrador.
    """
    message = "Solo el Administrador puede modificar estos registros."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return request.user.es_administrador()


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
