from django.db import transaction
from django.db.models import Max, Q, Sum
from rest_framework.exceptions import ValidationError

from apps_sirae.asistencia_diaria.models import AsistenciaDiaria
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.contratos_seccion_menu.models import ContratoSeccionMenu
from apps_sirae.grados.models import Grados
from apps_sirae.jornadas.models import Jornada
from apps_sirae.menus.models import Menu
from apps_sirae.sedes.models import Sede
from apps_sirae.usuarios.models import Usuario

from .models import HistorialConfiguracionSede, SedeJornada, SedeJornadaGrado


def _cupos_no_negativos(valor, campo):
    if isinstance(valor, bool) or not (
        isinstance(valor, int) or isinstance(valor, str) and valor.isdecimal()
    ):
        raise ValidationError({campo: 'Debe ser un número entero mayor o igual a cero.'})

    cupos = int(valor)
    if cupos < 0:
        raise ValidationError({campo: 'Debe ser un número entero mayor o igual a cero.'})
    return cupos


def _contratos_sede(sede, jornada_id=None):
    contratos = Contrato.objects.filter(id_sede_id=sede.id_sede)
    if jornada_id is not None:
        contratos = contratos.filter(id_jornada_id=jornada_id)
    return contratos


def _cupos_autorizados_sede(sede):
    return _contratos_sede(sede).aggregate(total=Sum('cupos'))['total'] or 0


def _asistencia_maxima(sede, grado_id):
    usuarios_sede = Usuario.objects.filter(
        id_sede_id=sede.id_sede,
    ).values_list('id_usuario', flat=True)
    return AsistenciaDiaria.objects.filter(
        id_grado_id=grado_id,
        id_usuario_manipuladora__in=usuarios_sede,
    ).aggregate(maximo=Max('ninos_presentes'))['maximo'] or 0


def _menu_maximo(sede, jornada_id):
    contratos = _contratos_sede(sede, jornada_id)
    contrato_ids = contratos.values_list('id_contrato', flat=True)
    return Menu.objects.filter(
        id_contrato__in=contrato_ids,
        id_jornada_id=jornada_id,
    ).aggregate(maximo=Max('ninos_presentes'))['maximo'] or 0


def _tiene_secciones_asociadas(sede, jornada_id):
    return ContratoSeccionMenu.objects.filter(
        id_contrato__id_sede_id=sede.id_sede,
    ).filter(
        Q(id_contrato__id_jornada_id=jornada_id)
        | Q(id_seccion__id_jornada_id=jornada_id)
    ).exists()


def _snapshot(sede):
    configuraciones = SedeJornada.objects.filter(
        id_sede=sede,
    ).select_related('id_jornada').prefetch_related('grados_atendidos__id_grado')
    return [
        {
            'id_jornada': configuracion.id_jornada_id,
            'nombre_jornada': configuracion.id_jornada.nombre_jornada or '',
            'cupos': configuracion.cupos,
            'grados': [
                {
                    'id_grado': asignacion.id_grado_id,
                    'nombre_grado': asignacion.id_grado.nombre_grado,
                    'cupos': asignacion.cupos,
                }
                for asignacion in sorted(
                    (a for a in configuracion.grados_atendidos.all() if a.estado == 'ACTIVO'),
                    key=lambda item: item.id_grado_id,
                )
            ],
        }
        for configuracion in configuraciones.order_by('id_jornada__nombre_jornada')
    ]


def guardar_configuracion_sede(sede, usuario, jornadas):
    if not isinstance(jornadas, list):
        raise ValidationError({'jornadas': 'Debe ser una lista de jornadas configuradas.'})

    jornadas_normalizadas = []
    jornada_ids = set()
    for indice, item in enumerate(jornadas):
        if not isinstance(item, dict):
            raise ValidationError({'jornadas': f'La jornada en la posición {indice + 1} no es válida.'})

        jornada_id = item.get('id_jornada')
        try:
            jornada_id = int(jornada_id)
        except (TypeError, ValueError):
            raise ValidationError({'id_jornada': 'Selecciona una jornada válida.'}) from None
        if jornada_id in jornada_ids:
            raise ValidationError({'jornadas': 'No se permiten jornadas repetidas para una sede.'})
        jornada_ids.add(jornada_id)

        cupos = _cupos_no_negativos(item.get('cupos', 0), 'cupos')
        grados = item.get('grados', [])
        if not isinstance(grados, list):
            raise ValidationError({'grados': 'Los cupos por grado deben enviarse como una lista.'})

        grados_normalizados = []
        grado_ids = set()
        for grado_item in grados:
            if not isinstance(grado_item, dict):
                raise ValidationError({'grados': 'Cada asignación de grado debe ser un objeto.'})
            try:
                grado_id = int(grado_item.get('id_grado'))
            except (TypeError, ValueError):
                raise ValidationError({'id_grado': 'Selecciona un grado válido.'}) from None
            if grado_id in grado_ids:
                raise ValidationError({'grados': 'No se permiten grados repetidos en una jornada.'})
            grado_ids.add(grado_id)
            estado_raw = grado_item.get('estado')
            estado_normalizado = None
            if estado_raw is not None and str(estado_raw).strip() != '':
                estado_normalizado = str(estado_raw).strip().upper()
                if estado_normalizado not in {'ACTIVO', 'INACTIVO'}:
                    raise ValidationError({'estado': 'El estado del grado debe ser ACTIVO o INACTIVO.'})

            grados_normalizados.append({
                'id_grado': grado_id,
                'cupos': _cupos_no_negativos(grado_item.get('cupos', 0), 'cupos'),
                'estado': estado_normalizado,
            })

        if sum(grado['cupos'] for grado in grados_normalizados) > cupos:
            raise ValidationError({
                'grados': f'La suma de cupos por grado supera los {cupos} cupos de la jornada {jornada_id}.',
            })
        jornadas_normalizadas.append({
            'id_jornada': jornada_id,
            'cupos': cupos,
            'grados': grados_normalizados,
        })

    jornada_catalogo = {
        jornada.id_jornada: jornada
        for jornada in Jornada.objects.filter(id_jornada__in=jornada_ids)
    }
    if len(jornada_catalogo) != len(jornada_ids):
        raise ValidationError({'jornadas': 'Una o más jornadas ya no existen en el Banco de Datos.'})

    grado_ids = {
        grado['id_grado']
        for jornada in jornadas_normalizadas
        for grado in jornada['grados']
    }
    grados_catalogo = set(
        Grados.objects.filter(id_grado__in=grado_ids).values_list('id_grado', flat=True)
    )
    if grados_catalogo != grado_ids:
        raise ValidationError({'grados': 'Uno o más grados ya no existen en el Banco de Datos.'})

    with transaction.atomic():
        sede_bloqueada = Sede.objects.select_for_update().get(pk=sede.pk)
        configuraciones_actuales = {
            item.id_jornada_id: item
            for item in SedeJornada.objects.select_for_update()
            .filter(id_sede=sede_bloqueada)
            .prefetch_related('grados_atendidos')
        }
        antes = _snapshot(sede_bloqueada)
        total_sede = sum(item['cupos'] for item in jornadas_normalizadas)
        cupos_autorizados = _cupos_autorizados_sede(sede_bloqueada)
        if total_sede > cupos_autorizados:
            raise ValidationError({
                'jornadas': (
                    f'La distribución suma {total_sede} cupos y supera los '
                    f'{cupos_autorizados} autorizados para esta sede.'
                ),
            })

        otras_sedes = SedeJornada.objects.filter(
            id_sede__id_institucion_id=sede_bloqueada.id_institucion_id,
        ).exclude(id_sede=sede_bloqueada)
        cupos_distribuidos_otros = otras_sedes.aggregate(total=Sum('cupos'))['total'] or 0
        cupos_autorizados_institucion = Contrato.objects.filter(
            id_institucion_id=sede_bloqueada.id_institucion_id,
        ).aggregate(total=Sum('cupos'))['total'] or 0
        if cupos_distribuidos_otros + total_sede > cupos_autorizados_institucion:
            raise ValidationError({
                'jornadas': 'La suma distribuida entre las sedes supera los cupos autorizados del contrato institucional.',
            })

        recibidas = {item['id_jornada']: item for item in jornadas_normalizadas}
        retiradas = set(configuraciones_actuales) - set(recibidas)
        for jornada_id in retiradas:
            configuracion = configuraciones_actuales[jornada_id]
            cupos_contrato = _contratos_sede(sede_bloqueada, jornada_id).aggregate(
                total=Sum('cupos'),
            )['total'] or 0
            tiene_cupos_grado = configuracion.grados_atendidos.filter(estado='ACTIVO', cupos__gt=0).exists()
            tiene_asistencia = any(
                _asistencia_maxima(sede_bloqueada, asignacion.id_grado_id) > 0
                for asignacion in configuracion.grados_atendidos.all()
                if asignacion.estado == 'ACTIVO'
            )
            if (
                configuracion.cupos > 0
                or cupos_contrato > 0
                or tiene_cupos_grado
                or tiene_asistencia
                or _tiene_secciones_asociadas(sede_bloqueada, jornada_id)
                or _menu_maximo(sede_bloqueada, jornada_id) > 0
            ):
                raise ValidationError({
                    'jornadas': (
                        f'No se puede retirar la jornada {jornada_id}: tiene cupos, '
                        'secciones o registros operativos asociados.'
                    ),
                })

        for item in jornadas_normalizadas:
            jornada_id = item['id_jornada']
            actual = configuraciones_actuales.get(jornada_id)
            cupos_grados = {grado['id_grado']: grado['cupos'] for grado in item['grados']}
            grados_actuales = {
                asignacion.id_grado_id: asignacion
                for asignacion in actual.grados_atendidos.all()
            } if actual else {}
            grados_activos_actuales = {
                grado_id
                for grado_id, asignacion in grados_actuales.items()
                if asignacion.estado == 'ACTIVO'
            }
            for grado_id in grados_activos_actuales | set(cupos_grados):
                cupos_nuevos = cupos_grados.get(grado_id, 0)
                asistencia_maxima = _asistencia_maxima(sede_bloqueada, grado_id)
                if cupos_nuevos < asistencia_maxima:
                    grado_nombre = Grados.objects.get(pk=grado_id).nombre_grado
                    raise ValidationError({
                        'grados': (
                            f'No se pueden reducir los cupos de {grado_nombre} por debajo '
                            f'de los {asistencia_maxima} estudiantes presentes registrados en esta sede.'
                        ),
                    })

            menu_maximo = _menu_maximo(sede_bloqueada, jornada_id)
            if item['cupos'] < menu_maximo:
                raise ValidationError({
                    'cupos': (
                        f'No se puede reducir la jornada por debajo de los '
                        f'{menu_maximo} beneficiarios de menús ya registrados.'
                    ),
                })

            configuracion, _ = SedeJornada.objects.update_or_create(
                id_sede=sede_bloqueada,
                id_jornada_id=jornada_id,
                defaults={'cupos': item['cupos']},
            )
            grados_activos_o_conservados = set()
            for grado in item['grados']:
                estado_objetivo = grado['estado']
                if estado_objetivo is None:
                    estado_objetivo = 'ACTIVO' if grado['cupos'] > 0 else 'INACTIVO'

                if estado_objetivo == 'ACTIVO' or grado['id_grado'] in grados_actuales:
                    SedeJornadaGrado.objects.update_or_create(
                        id_sede_jornada=configuracion,
                        id_grado_id=grado['id_grado'],
                        defaults={
                            'cupos': 0 if estado_objetivo == 'INACTIVO' else grado['cupos'],
                            'estado': estado_objetivo,
                        },
                    )
                    if estado_objetivo == 'ACTIVO':
                        grados_activos_o_conservados.add(grado['id_grado'])

            configuracion.grados_atendidos.exclude(
                id_grado_id__in=grados_activos_o_conservados
            ).update(estado='INACTIVO', cupos=0)

        if retiradas:
            SedeJornada.objects.filter(
                id_sede=sede_bloqueada,
                id_jornada_id__in=retiradas,
            ).delete()

        despues = _snapshot(sede_bloqueada)
        if antes != despues:
            HistorialConfiguracionSede.objects.create(
                id_sede=sede_bloqueada,
                usuario=usuario,
                valores_anteriores={'jornadas': antes},
                valores_nuevos={'jornadas': despues},
            )

    return despues
