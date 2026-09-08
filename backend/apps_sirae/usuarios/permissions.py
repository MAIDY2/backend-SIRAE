from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminRole(BasePermission):
    """
    Permiso que autoriza únicamente a usuarios con el rol de Administrador.
    """
    message = "Acceso restringido: Se requiere el rol de Administrador."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_administrador()


class IsSupervisorRole(BasePermission):
    """
    Permiso que autoriza a usuarios con rol de Supervisor (o Coordinador).
    """
    message = "Acceso restringido: Se requiere el rol de Supervisor."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.es_supervisor()


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


class IsNotAdminRole(BasePermission):
    """
    Regla de negocio PAE:
    El Administrador NO selecciona el menú diario ni registra asistencia diaria
    (no reemplaza la función operativa de la jefa).
    """
    message = "El rol Administrador no está autorizado para realizar operaciones exclusivas de la Jefa de manipuladoras."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return not request.user.es_administrador()
