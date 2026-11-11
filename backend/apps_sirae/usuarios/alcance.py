from django.db.models import Q

from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.instituciones.models import Institucion
from apps_sirae.jornadas.models import Jornada
from apps_sirae.sede_jornada.models import SedeJornada
from apps_sirae.sedes.models import Sede


def usuario_puede_consultar_alcance(usuario):
    """
    Roles autorizados para consultar gramajes por institución, sede y jornada.
    """
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return False
    return (
        usuario.es_super_administrador()
        or usuario.es_supervisor()
        or usuario.es_administrador()
        or usuario.es_jefa_manipuladoras()
    )


def obtener_ids_instituciones_supervisor(usuario):
    """
    Retorna el conjunto de IDs de instituciones asignadas al supervisor
    por relación directa, contratos o institución principal.
    """
    if not usuario or not usuario.es_supervisor():
        return set()

    institucion_ids = set(
        usuario.instituciones_asignadas.values_list('id_institucion_id', flat=True)
    )

    contratos_qs = Contrato.objects.filter(id_usuario_supervisor=usuario)
    for id_inst, id_sede_inst in contratos_qs.values_list(
        'id_institucion_id', 'id_sede__id_institucion_id'
    ):
        if id_inst:
            institucion_ids.add(id_inst)
        if id_sede_inst:
            institucion_ids.add(id_sede_inst)

    if usuario.id_institucion_id:
        institucion_ids.add(usuario.id_institucion_id)

    institucion_ids.discard(None)
    return institucion_ids


def obtener_instituciones_autorizadas(usuario, queryset=None):
    """
    Filtra las instituciones visibles estrictamente según el rol del usuario.
    """
    qs = queryset if queryset is not None else Institucion.objects.all()
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return qs.none()

    if usuario.es_super_administrador():
        return qs

    if usuario.es_supervisor():
        ids = obtener_ids_instituciones_supervisor(usuario)
        return qs.filter(id_institucion__in=ids) if ids else qs.none()

    if usuario.es_administrador():
        if not usuario.id_institucion_id:
            return qs.none()
        return qs.filter(id_institucion=usuario.id_institucion_id)

    if usuario.es_jefa_manipuladoras() or usuario.es_manipuladora():
        inst_id = usuario.id_institucion_id
        if not inst_id and usuario.id_sede_id:
            inst_id = (
                Sede.objects.filter(pk=usuario.id_sede_id)
                .values_list('id_institucion_id', flat=True)
                .first()
            )
        return qs.filter(id_institucion=inst_id) if inst_id else qs.none()

    return qs.none()


def obtener_sedes_autorizadas(usuario, queryset=None):
    """
    Filtra las sedes visibles estrictamente según el rol del usuario.
    """
    qs = queryset if queryset is not None else Sede.objects.all()
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return qs.none()

    if usuario.es_super_administrador():
        return qs

    if usuario.es_supervisor():
        filtro = (
            Q(id_institucion__supervisores_asignados__id_supervisor=usuario)
            | Q(id_institucion__contratos__id_usuario_supervisor=usuario)
            | Q(contratos__id_usuario_supervisor=usuario)
        )
        if usuario.id_institucion_id:
            filtro |= Q(id_institucion_id=usuario.id_institucion_id)
        return qs.filter(filtro).distinct()

    if usuario.es_administrador():
        if not usuario.id_institucion_id:
            return qs.none()
        return qs.filter(id_institucion_id=usuario.id_institucion_id)

    if usuario.es_jefa_manipuladoras() or usuario.es_manipuladora():
        if not usuario.id_sede_id:
            return qs.none()
        return qs.filter(id_sede=usuario.id_sede_id)

    return qs.none()


def obtener_sede_jornadas_autorizadas(usuario, queryset=None):
    """
    Retorna las combinaciones sede + jornada accesibles al usuario.
    Para Jefa de manipuladoras exige sede y jornada asignadas explícitamente.
    """
    qs = queryset if queryset is not None else SedeJornada.objects.all()
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return qs.none()

    if usuario.es_super_administrador():
        return qs

    if usuario.es_supervisor() or usuario.es_administrador():
        sedes_qs = obtener_sedes_autorizadas(usuario)
        return qs.filter(id_sede__in=sedes_qs)

    if usuario.es_jefa_manipuladoras() or usuario.es_manipuladora():
        if not usuario.id_sede_id or not usuario.id_jornada_id:
            return qs.none()
        return qs.filter(
            id_sede_id=usuario.id_sede_id,
            id_jornada_id=usuario.id_jornada_id,
        )

    return qs.none()


def obtener_alertas_asignacion_usuario(usuario):
    """
    Genera mensajes informativos si el usuario autenticado carece de asignación
    institucional, de sede o de jornada requerida para consultar su alcance.
    """
    alertas = []
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return alertas

    if usuario.es_administrador() and not usuario.id_institucion_id:
        alertas.append({
            'tipo': 'ALCANCE_INCOMPLETO',
            'severidad': 'ALTA',
            'mensaje': (
                'Tu usuario Administrador no tiene una institución asignada; '
                'solicita al Super Administrador asociar tu institución.'
            ),
        })
    elif usuario.es_jefa_manipuladoras():
        if not usuario.id_sede_id:
            alertas.append({
                'tipo': 'ALCANCE_INCOMPLETO',
                'severidad': 'ALTA',
                'mensaje': (
                    'Tu perfil de Jefa de manipuladoras no tiene una sede asignada. '
                    'No se mostrará información de otras sedes.'
                ),
            })
        if not usuario.id_jornada_id:
            alertas.append({
                'tipo': 'ALCANCE_INCOMPLETO',
                'severidad': 'ALTA',
                'mensaje': (
                    'Tu perfil de Jefa de manipuladoras no tiene una jornada asignada. '
                    'Solicita al Administrador asociar tu sede y jornada para habilitar la consulta.'
                ),
            })
    return alertas


def describir_alcance_usuario(usuario):
    """
    Resume el alcance autorizado y las opciones disponibles de institución, sede y jornada.
    """
    instituciones_qs = obtener_instituciones_autorizadas(usuario).order_by('nombre_institucion')
    sedes_qs = obtener_sedes_autorizadas(usuario).select_related('id_institucion').order_by('nombre_sede')
    sede_jornadas_qs = (
        obtener_sede_jornadas_autorizadas(usuario)
        .select_related('id_sede', 'id_sede__id_institucion', 'id_jornada')
        .order_by('id_jornada__nombre_jornada')
    )

    if usuario.es_super_administrador():
        jornadas_qs = Jornada.objects.all().order_by('nombre_jornada')
        rol_nivel = 'SUPERADMINISTRADOR'
    elif usuario.es_jefa_manipuladoras():
        jornadas_qs = (
            Jornada.objects.filter(pk=usuario.id_jornada_id)
            if usuario.id_jornada_id
            else Jornada.objects.none()
        )
        rol_nivel = 'JEFA_MANIPULADORAS'
    else:
        jornada_ids = list(
            sede_jornadas_qs.values_list('id_jornada_id', flat=True).distinct()
        )
        jornadas_qs = Jornada.objects.filter(pk__in=jornada_ids).order_by('nombre_jornada')
        rol_nivel = 'SUPERVISOR' if usuario.es_supervisor() else 'ADMINISTRADOR'

    return {
        'rol': usuario.rol.nombre if usuario.rol else ('Super Administrador' if usuario.is_superuser else ''),
        'rol_nivel': rol_nivel,
        'puede_filtrar_institucion': usuario.es_super_administrador() or usuario.es_supervisor(),
        'puede_filtrar_sede': not usuario.es_jefa_manipuladoras(),
        'puede_filtrar_jornada': not usuario.es_jefa_manipuladoras(),
        'id_institucion_asignada': usuario.id_institucion_id,
        'id_sede_asignada': usuario.id_sede_id,
        'id_jornada_asignada': usuario.id_jornada_id,
        'alertas_alcance': obtener_alertas_asignacion_usuario(usuario),
        'instituciones_disponibles': [
            {
                'id_institucion': inst.id_institucion,
                'nombre_institucion': inst.nombre_institucion,
            }
            for inst in instituciones_qs
        ],
        'sedes_disponibles': [
            {
                'id_sede': sede.id_sede,
                'nombre_sede': sede.nombre_sede,
                'id_institucion': sede.id_institucion_id,
                'nombre_institucion': sede.id_institucion.nombre_institucion if sede.id_institucion else '',
            }
            for sede in sedes_qs
        ],
        'jornadas_disponibles': [
            {
                'id_jornada': j.id_jornada,
                'nombre_jornada': j.nombre_jornada,
            }
            for j in jornadas_qs
        ],
    }

