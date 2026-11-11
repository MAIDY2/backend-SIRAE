"""
Matriz Estricta de Comunicación (Control de Permisos por Rol)
SIRAE PAE

Reglas de negocio:
- CA-01 (Manipuladora Jefe ⇄ Supervisor): Comunicación bidireccional.
- CA-02 (Supervisor ⇄ Administrador/Superadministrador): Comunicación bidireccional.
- CA-03 (Manipuladora Base → Manipuladora Jefe): Envío de novedades y evidencias.
- CA-04 (Manipuladora Jefe → Manipuladora Base): Envío de directrices y avisos.
- CA-05 (Bloqueo de Envíos No Autorizados): Cualquier otro intento es rechazado con 403 Forbidden.
"""

from rest_framework import permissions
from apps_sirae.usuarios.models import Usuario


MENSAJE_ERROR_PERMISOS = "No tienes permisos para comunicarte con este usuario"


def puede_comunicarse(remitente: Usuario, destinatario: Usuario) -> bool:
    """
    Verifica si el remitente tiene autorización para enviar mensajes al destinatario
    según la matriz estricta de comunicación del SIRAE (CA-01 a CA-05).
    """
    if not remitente or not destinatario:
        return False

    remitente_id = getattr(remitente, 'id_usuario', None)
    destinatario_id = getattr(destinatario, 'id_usuario', None)

    if remitente_id is None or destinatario_id is None:
        return False

    # No se permite enviarse mensajes a uno mismo
    if remitente_id == destinatario_id:
        return False

    # CA-01 & CA-04: Manipuladora Jefe
    if remitente.es_jefa_manipuladoras():
        # Puede comunicarse con Supervisor (CA-01) o Manipuladora Base (CA-04)
        return destinatario.es_supervisor() or destinatario.es_manipuladora()

    # CA-01 & CA-02: Supervisor
    if remitente.es_supervisor():
        # Puede comunicarse con Manipuladora Jefe (CA-01) o Administrador/Superadministrador (CA-02)
        return (
            destinatario.es_jefa_manipuladoras()
            or destinatario.es_administrador()
            or destinatario.es_super_administrador()
        )

    # CA-02: Administrador o Superadministrador
    if remitente.es_administrador() or remitente.es_super_administrador():
        # Puede comunicarse con Supervisor (CA-02)
        return destinatario.es_supervisor()

    # CA-03: Manipuladora Base
    if remitente.es_manipuladora():
        # Puede comunicarse únicamente con Manipuladora Jefe (CA-03)
        return destinatario.es_jefa_manipuladoras()

    # Bloqueo estricto para cualquier otro rol / caso (CA-05)
    return False


def get_contactos_permitidos_para_usuario(usuario: Usuario):
    """
    Retorna los usuarios activos con los que el usuario logueado tiene permiso
    de comunicarse según su rol.
    """
    if not usuario or not usuario.is_authenticated:
        return Usuario.objects.none()

    qs = Usuario.objects.filter(is_active=True).exclude(
        id_usuario=usuario.id_usuario
    ).select_related('rol')

    permitidos = [dest for dest in qs if puede_comunicarse(usuario, dest)]
    permitidos_ids = [u.id_usuario for u in permitidos]

    return qs.filter(id_usuario__in=permitidos_ids)
