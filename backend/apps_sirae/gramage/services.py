from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.detalle_plato.models import DetallePlato
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.menus.models import Menu
from apps_sirae.receta_componente.models import RecetaComponente
from apps_sirae.usuarios.alcance import (
    describir_alcance_usuario,
    obtener_instituciones_autorizadas,
    obtener_sede_jornadas_autorizadas,
    obtener_sedes_autorizadas,
    usuario_puede_consultar_alcance,
)


def _parse_int_or_none(valor, nombre_parametro):
    if valor in (None, '', 'null', 'undefined'):
        return None
    try:
        return int(valor)
    except (TypeError, ValueError):
        raise PermissionDenied(f"El parámetro '{nombre_parametro}' debe ser numérico válido.")


def _parse_lista_enteros(valor):
    if not valor:
        return []
    ids = []
    for parte in str(valor).split(','):
        parte = parte.strip()
        if not parte:
            continue
        try:
            ids.append(int(parte))
        except ValueError:
            continue
    return ids


def _obtener_productos_requeridos_sede_jornada(id_sede, id_jornada, fecha=None, ingredientes_extra_ids=None):
    """
    Identifica los ingredientes requeridos según menús/minutas y recetas asociadas
    a la sede y jornada, más los ingredientes consultados explícitamente si los hay.
    Retorna dict[id_ingrediente -> {'ingrediente': Ingrediente, 'origenes': set[str]}].
    """
    requeridos = {}

    contratos_sede_ids = list(
        Contrato.objects.filter(id_sede_id=id_sede).values_list('id_contrato', flat=True)
    )
    contratos_sede_jornada_ids = set(
        Contrato.objects.filter(
            id_sede_id=id_sede, id_jornada_id=id_jornada
        ).values_list('id_contrato', flat=True)
    )

    if contratos_sede_ids:
        menus_qs = Menu.objects.filter(
            id_contrato__in=contratos_sede_ids
        ).filter(
            Q(id_jornada_id=id_jornada) | Q(id_contrato__in=contratos_sede_jornada_ids)
        ).exclude(
            Q(estado__iexact='INACTIVO') | Q(estado__iexact='CANCELADO')
        )
        if fecha:
            menus_qs = menus_qs.filter(fecha=fecha)

        menus_por_id = {m.id_menu: m for m in menus_qs}
        if menus_por_id:
            detalles = (
                DetallePlato.objects.filter(id_menu__in=list(menus_por_id.keys()))
                .select_related('id_plato')
            )
            plato_a_origen = {}
            for det in detalles:
                if not det.id_plato_id:
                    continue
                menu_obj = menus_por_id.get(det.id_menu)
                nombre_plato = getattr(det.id_plato, 'nombre_plato', None) or f"Plato #{det.id_plato_id}"
                etiqueta_menu = (menu_obj.fecha if menu_obj and menu_obj.fecha else det.id_menu)
                etiqueta = f"Menú {etiqueta_menu} · {nombre_plato}"
                plato_a_origen.setdefault(det.id_plato_id, set()).add(etiqueta)

            if plato_a_origen:
                componentes = RecetaComponente.objects.filter(
                    id_plato_id__in=plato_a_origen.keys(),
                    id_ingrediente__isnull=False,
                ).select_related('id_ingrediente', 'id_ingrediente__id_unidad_medida')

                for comp in componentes:
                    ing = comp.id_ingrediente
                    if not ing:
                        continue
                    entry = requeridos.setdefault(
                        ing.id_ingrediente,
                        {'ingrediente': ing, 'origenes': set()},
                    )
                    entry['origenes'].update(plato_a_origen.get(comp.id_plato_id, {'Receta asignada'}))

    if ingredientes_extra_ids:
        extras = Ingrediente.objects.filter(
            id_ingrediente__in=ingredientes_extra_ids
        ).select_related('id_unidad_medida')
        for ing in extras:
            entry = requeridos.setdefault(
                ing.id_ingrediente,
                {'ingrediente': ing, 'origenes': set()},
            )
            entry['origenes'].add('Producto requerido en consulta')

    return requeridos


def _serializar_gramaje_consulta(g):
    ing = g.id_ingrediente
    unidad = g.id_unidad_medida
    unidad_inv = ing.id_unidad_medida if ing else None
    cat = ing.id_categoria_inventario if ing else None
    tipo_cons = (ing.tipo_conservacion if ing else None) or 'no_perecedero'

    return {
        'id_gramaje': g.id_gramaje,
        'id_ingrediente': g.id_ingrediente_id,
        'nombre_ingrediente': ing.nombre_ingrediente if ing else '',
        'categoria': getattr(cat, 'nombre_categoria', None) or getattr(cat, 'nombre', None) or '',
        'tipo_conservacion': tipo_cons,
        'tipo_alimento': 'Perecedero' if tipo_cons == 'perecedero' else 'No perecedero',
        'cantidad_gramaje': float(g.cantidad_gramaje) if g.cantidad_gramaje is not None else None,
        'id_unidad_medida': g.id_unidad_medida_id,
        'nombre_unidad_medida': unidad.nombre if unidad else '',
        'abreviatura_unidad_medida': unidad.abreviatura if unidad else '',
        'tipo_magnitud_unidad': unidad.tipo_magnitud if unidad else '',
        'unidad_base_producto': (
            {
                'id_unidad_medida': unidad_inv.id_unidad_medida,
                'nombre': unidad_inv.nombre,
                'abreviatura': unidad_inv.abreviatura,
                'tipo_magnitud': unidad_inv.tipo_magnitud,
            }
            if unidad_inv
            else None
        ),
        'contexto_aplicacion': g.contexto_aplicacion,
        'contexto_aplicacion_display': g.get_contexto_aplicacion_display(),
        'descripcion': g.descripcion or '',
        'estado': g.estado,
    }


def consultar_gramajes_por_alcance(usuario, query_params):
    """
    Consulta los gramajes aplicables según institución, sede y jornada estrictamente dentro
    del alcance autorizado para el usuario, identificando grados atendidos, unidades de medida
    y alertas por ausencia de configuración sin asumir cantidades arbitrarias.
    """
    if not usuario_puede_consultar_alcance(usuario):
        raise PermissionDenied(
            "Tu rol no tiene autorización para consultar la parametrización de gramajes por alcance."
        )

    id_institucion = _parse_int_or_none(query_params.get('id_institucion'), 'id_institucion')
    id_sede = _parse_int_or_none(query_params.get('id_sede'), 'id_sede')
    id_jornada = _parse_int_or_none(query_params.get('id_jornada'), 'id_jornada')
    id_grado = _parse_int_or_none(query_params.get('id_grado'), 'id_grado')
    fecha = query_params.get('fecha') or None
    ingredientes_filtro_ids = _parse_lista_enteros(
        query_params.get('id_ingrediente') or query_params.get('productos_requeridos')
    )

    instituciones_auth = obtener_instituciones_autorizadas(usuario)
    sedes_auth = obtener_sedes_autorizadas(usuario)
    sede_jornadas_auth = obtener_sede_jornadas_autorizadas(usuario)

    # Validar explícitamente que no se consulten filtros fuera del alcance institucional
    if id_institucion is not None and not instituciones_auth.filter(pk=id_institucion).exists():
        raise PermissionDenied(
            "No tienes autorización para consultar gramajes de una institución fuera de tu alcance."
        )
    if id_sede is not None and not sedes_auth.filter(pk=id_sede).exists():
        raise PermissionDenied(
            "No tienes autorización para consultar gramajes de una sede fuera de tu alcance."
        )
    if (
        id_jornada is not None
        and usuario.es_jefa_manipuladoras()
        and usuario.id_jornada_id != id_jornada
    ):
        raise PermissionDenied(
            "No tienes autorización para consultar gramajes de una jornada diferente a la asignada."
        )

    sj_qs = (
        sede_jornadas_auth.select_related('id_sede', 'id_sede__id_institucion', 'id_jornada')
        .prefetch_related('grados_atendidos__id_grado__id_grupo_gramaje')
        .order_by('id_sede__id_institucion__nombre_institucion', 'id_sede__nombre_sede', 'id_jornada__nombre_jornada')
    )
    if id_institucion is not None:
        sj_qs = sj_qs.filter(id_sede__id_institucion_id=id_institucion)
    if id_sede is not None:
        sj_qs = sj_qs.filter(id_sede_id=id_sede)
    if id_jornada is not None:
        sj_qs = sj_qs.filter(id_jornada_id=id_jornada)

    # Indexar gramajes activos por grado una sola vez
    gramajes_activos = (
        Gramage.objects.filter(estado='ACTIVO')
        .select_related(
            'id_ingrediente',
            'id_ingrediente__id_categoria_inventario',
            'id_ingrediente__id_unidad_medida',
            'id_grado',
            'id_grado__id_grupo_gramaje',
            'id_unidad_medida',
        )
        .order_by('id_ingrediente__nombre_ingrediente', 'contexto_aplicacion')
    )
    gramajes_por_grado = {}
    for g in gramajes_activos:
        if not g.id_grado_id:
            continue
        gramajes_por_grado.setdefault(g.id_grado_id, []).append(g)

    sede_jornadas_resultado = []
    alertas_faltantes = []

    for sj in sj_qs:
        sede = sj.id_sede
        institucion = sede.id_institucion if sede else None
        jornada = sj.id_jornada

        requeridos = _obtener_productos_requeridos_sede_jornada(
            sj.id_sede_id,
            sj.id_jornada_id,
            fecha=fecha,
            ingredientes_extra_ids=ingredientes_filtro_ids,
        )

        atenciones = [
            rel for rel in sj.grados_atendidos.all()
            if rel.estado == 'ACTIVO' and rel.id_grado and rel.id_grado.estado == 'ACTIVO'
        ]
        if id_grado is not None:
            atenciones = [rel for rel in atenciones if rel.id_grado_id == id_grado]

        grados_payload = []
        alertas_sj = []

        if not atenciones:
            msg_sin_grados = (
                f"La sede '{sede.nombre_sede}' en jornada '{jornada.nombre_jornada}' "
                "no tiene grados escolares configurados."
            )
            alerta_cfg = {
                'tipo': 'SIN_GRADOS_CONFIGURADOS',
                'severidad': 'MEDIA',
                'id_institucion': institucion.id_institucion if institucion else None,
                'nombre_institucion': institucion.nombre_institucion if institucion else '',
                'id_sede': sj.id_sede_id,
                'nombre_sede': sede.nombre_sede if sede else '',
                'id_jornada': sj.id_jornada_id,
                'nombre_jornada': jornada.nombre_jornada if jornada else '',
                'id_grado': None,
                'nombre_grado': None,
                'id_ingrediente': None,
                'nombre_ingrediente': None,
                'cantidad_gramaje': None,
                'mensaje': msg_sin_grados,
            }
            alertas_sj.append(alerta_cfg)
            alertas_faltantes.append(alerta_cfg)

        for rel in atenciones:
            grado = rel.id_grado
            grupo = grado.id_grupo_gramaje
            gramajes_grado_todos = gramajes_por_grado.get(grado.id_grado, [])
            if ingredientes_filtro_ids:
                gramajes_visibles = [
                    g for g in gramajes_grado_todos
                    if g.id_ingrediente_id in ingredientes_filtro_ids
                ]
            else:
                gramajes_visibles = gramajes_grado_todos

            ingredientes_cubiertos = {
                g.id_ingrediente_id
                for g in gramajes_grado_todos
                if g.id_ingrediente_id and g.cantidad_gramaje is not None and g.cantidad_gramaje > 0
            }

            alertas_grado = []
            for ing_id, req_info in requeridos.items():
                if ing_id not in ingredientes_cubiertos:
                    ing = req_info['ingrediente']
                    origen_txt = ', '.join(sorted(req_info['origenes']))
                    alerta = {
                        'tipo': 'FALTA_GRAMAJE_REQUERIDO',
                        'severidad': 'ALTA',
                        'id_institucion': institucion.id_institucion if institucion else None,
                        'nombre_institucion': institucion.nombre_institucion if institucion else '',
                        'id_sede': sj.id_sede_id,
                        'nombre_sede': sede.nombre_sede if sede else '',
                        'id_jornada': sj.id_jornada_id,
                        'nombre_jornada': jornada.nombre_jornada if jornada else '',
                        'id_grado': grado.id_grado,
                        'nombre_grado': grado.nombre_grado,
                        'id_ingrediente': ing.id_ingrediente,
                        'nombre_ingrediente': ing.nombre_ingrediente,
                        'origen_requisito': origen_txt,
                        'cantidad_gramaje': None,
                        'mensaje': (
                            f"El grado '{grado.nombre_grado}' ({sede.nombre_sede} - "
                            f"{jornada.nombre_jornada}) no tiene un gramaje activo configurado para el "
                            f"producto requerido '{ing.nombre_ingrediente}' ({origen_txt}). "
                            "No se asume ninguna cantidad arbitraria."
                        ),
                    }
                    alertas_grado.append(alerta)
                    alertas_sj.append(alerta)
                    alertas_faltantes.append(alerta)

            if not gramajes_grado_todos and not alertas_grado:
                alerta_vacio = {
                    'tipo': 'GRADO_SIN_GRAMAJES',
                    'severidad': 'MEDIA',
                    'id_institucion': institucion.id_institucion if institucion else None,
                    'nombre_institucion': institucion.nombre_institucion if institucion else '',
                    'id_sede': sj.id_sede_id,
                    'nombre_sede': sede.nombre_sede if sede else '',
                    'id_jornada': sj.id_jornada_id,
                    'nombre_jornada': jornada.nombre_jornada if jornada else '',
                    'id_grado': grado.id_grado,
                    'nombre_grado': grado.nombre_grado,
                    'id_ingrediente': None,
                    'nombre_ingrediente': None,
                    'cantidad_gramaje': None,
                    'mensaje': (
                        f"El grado '{grado.nombre_grado}' atendido en '{sede.nombre_sede}' "
                        f"(jornada {jornada.nombre_jornada}) aún no tiene gramajes activos configurados."
                    ),
                }
                alertas_grado.append(alerta_vacio)
                alertas_sj.append(alerta_vacio)
                alertas_faltantes.append(alerta_vacio)

            grados_payload.append({
                'id_grado': grado.id_grado,
                'nombre_grado': grado.nombre_grado,
                'nivel_educativo': grado.nivel_educativo,
                'nivel_educativo_display': grado.get_nivel_educativo_display(),
                'id_grupo_gramaje': grupo.id_grupo_gramaje if grupo else None,
                'nombre_grupo_gramaje': grupo.nombre if grupo else 'Sin grupo asignado',
                'cupos_grado': rel.cupos,
                'gramajes': [_serializar_gramaje_consulta(g) for g in gramajes_visibles],
                'alertas': alertas_grado,
                'tiene_alertas': len(alertas_grado) > 0,
            })

        sede_jornadas_resultado.append({
            'id_sede_jornada': sj.id_sede_jornada,
            'id_institucion': institucion.id_institucion if institucion else None,
            'nombre_institucion': institucion.nombre_institucion if institucion else '',
            'id_sede': sj.id_sede_id,
            'nombre_sede': sede.nombre_sede if sede else '',
            'id_jornada': sj.id_jornada_id,
            'nombre_jornada': jornada.nombre_jornada if jornada else '',
            'cupos_jornada': sj.cupos,
            'productos_requeridos': [
                {
                    'id_ingrediente': req['ingrediente'].id_ingrediente,
                    'nombre_ingrediente': req['ingrediente'].nombre_ingrediente,
                    'origenes': sorted(req['origenes']),
                }
                for req in sorted(
                    requeridos.values(),
                    key=lambda item: item['ingrediente'].nombre_ingrediente or '',
                )
            ],
            'grados_atendidos': grados_payload,
            'total_grados': len(grados_payload),
            'total_alertas': len(alertas_sj),
        })

    alcance = describir_alcance_usuario(usuario)

    return {
        'permisos': {
            'puede_modificar_gramajes': bool(usuario.es_super_administrador()),
        },
        'alcance': alcance,
        'filtros_aplicados': {
            'id_institucion': id_institucion,
            'id_sede': id_sede,
            'id_jornada': id_jornada,
            'id_grado': id_grado,
            'fecha': fecha,
            'id_ingrediente': ingredientes_filtro_ids,
        },
        'resumen': {
            'total_sede_jornadas': len(sede_jornadas_resultado),
            'total_grados_atendidos': sum(sj['total_grados'] for sj in sede_jornadas_resultado),
            'total_alertas': len(alertas_faltantes),
            'total_alertas_faltantes': sum(
                1 for a in alertas_faltantes if a['tipo'] == 'FALTA_GRAMAJE_REQUERIDO'
            ),
        },
        'alertas_alcance': alcance['alertas_alcance'],
        'alertas_faltantes': alertas_faltantes,
        'sede_jornadas': sede_jornadas_resultado,
    }
