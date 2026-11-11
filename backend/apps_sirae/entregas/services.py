from collections import defaultdict
from datetime import date
from decimal import Decimal
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.detalle_plato.models import DetallePlato
from apps_sirae.entregas.models import CalculoEntrega, Entrega
from apps_sirae.facturas_compra.models import InventarioCentral
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.inventario.models import Inventario
from apps_sirae.menus.models import Menu
from apps_sirae.receta_componente.models import RecetaComponente
from apps_sirae.sede_jornada.models import SedeJornada
from apps_sirae.sedes.models import Sede
from apps_sirae.tipos_mercado.models import TipoMercado
from apps_sirae.unidades_medida.services import (
    ErrorConversionUnidad,
    convertir_cantidad,
    formatear_cantidad_apropiada,
)
from apps_sirae.usuarios.alcance import (
    obtener_instituciones_autorizadas,
    obtener_sedes_autorizadas,
)

TOLERANCIA_EXCESO = Decimal('0.001')


def _es_usuario_bd(usuario) -> bool:
    return bool(usuario and getattr(usuario, 'is_authenticated', False) and hasattr(usuario, '_meta'))


def validar_alcance_sedes(usuario, sedes_qs, id_institucion=None):
    """
    Valida que el usuario autenticado tenga alcance autorizado sobre la institución y sedes consultadas.
    Lanza PermissionDenied si intenta operar fuera de su jurisdicción.
    """
    if not _es_usuario_bd(usuario):
        return sedes_qs

    if id_institucion is not None:
        inst_autorizadas = obtener_instituciones_autorizadas(usuario)
        if not inst_autorizadas.filter(pk=id_institucion).exists():
            raise PermissionDenied(
                'No tiene autorización para consultar o despachar entregas a esta institución.'
            )

    sedes_autorizadas = obtener_sedes_autorizadas(usuario, queryset=sedes_qs)
    if sedes_qs.exists() and not sedes_autorizadas.exists():
        raise PermissionDenied(
            'No tiene autorización para consultar o despachar entregas a la sede solicitada.'
        )
    return sedes_autorizadas


def _es_ingrediente_perecedero(ingrediente: Ingrediente) -> bool:
    """Clasifica el producto en perecedero vs no perecedero de forma consistente."""
    tipo_cons = (getattr(ingrediente, 'tipo_conservacion', None) or '').strip().lower()
    if tipo_cons == 'perecedero':
        return True
    if tipo_cons == 'no_perecedero':
        return False

    tipo_mercado = getattr(ingrediente, 'id_tipo_mercado', None)
    nombre_tm = (getattr(tipo_mercado, 'nombre_tipo', None) or '').strip().lower()
    if nombre_tm:
        if 'pereced' in nombre_tm and 'no' not in nombre_tm:
            return True
        if 'no' in nombre_tm or 'grano' in nombre_tm:
            return False

    cat = getattr(ingrediente, 'id_categoria_inventario', None)
    nombre_cat = (getattr(cat, 'nombre', None) or '').strip().lower()
    if any(p in nombre_cat for p in ('fruta', 'verdur', 'carn', 'lact', 'huev', 'pereced')):
        return True
    return False


def _nombre_unidad(unidad) -> str:
    if not unidad:
        return ''
    return getattr(unidad, 'abreviatura', None) or getattr(unidad, 'nombre', None) or getattr(unidad, 'nombre_unidad', '')


def _resolver_contrato_y_periodicidad(
    sede: Sede,
    id_contrato=None,
    id_jornada=None,
):
    """Obtiene el contrato vigente aplicable a la sede y sus días de periodicidad por tipo de alimento."""
    contratos_base = Contrato.objects.filter(id_institucion_id=sede.id_institucion_id).select_related(
        'id_jornada', 'id_sede', 'id_institucion'
    )

    if id_contrato:
        contrato_sel = contratos_base.filter(pk=id_contrato).first()
        if not contrato_sel:
            raise ValidationError({'id_contrato': 'El contrato indicado no pertenece a la institución de la sede.'})
        if contrato_sel.id_sede_id and contrato_sel.id_sede_id != sede.id_sede:
            raise ValidationError({'id_contrato': 'El contrato indicado pertenece a otra sede.'})
        contratos_aplicables = [contrato_sel]
    else:
        qs = list(contratos_base.order_by('-id_sede_id', '-fecha_inicio', '-id_contrato'))
        contratos_sede = [
            c for c in qs
            if c.id_sede_id == sede.id_sede
            and (not id_jornada or c.id_jornada_id in (None, int(id_jornada)))
        ]
        contratos_inst = [
            c for c in qs
            if c.id_sede_id is None
            and (not id_jornada or c.id_jornada_id in (None, int(id_jornada)))
        ]
        contratos_aplicables = contratos_sede or contratos_inst

        # Priorizar contratos activos/vigentes cuando existan
        activos = [
            c for c in contratos_aplicables
            if (c.estado or '').strip().lower() in ('activo', 'vigente', '')
        ]
        if activos:
            contratos_aplicables = activos

    contrato_principal = contratos_aplicables[0] if contratos_aplicables else None
    faltantes = []

    if contrato_principal:
        dias_per = contrato_principal.obtener_dias_cobertura(True)
        dias_no_per = contrato_principal.obtener_dias_cobertura(False)
        per_per = contrato_principal.periodicidad_perecederos or 'SEMANAL'
        per_no_per = contrato_principal.periodicidad_no_perecederos or 'MENSUAL'
    else:
        dias_per = 5
        dias_no_per = 20
        per_per = 'SEMANAL'
        per_no_per = 'MENSUAL'
        faltantes.append({
            'tipo': 'CONTRATO',
            'nivel': 'ADVERTENCIA',
            'mensaje': (
                f"La sede '{sede.nombre_sede}' no tiene un contrato PAE parametrizado; "
                "se utilizan días por defecto (5 días perecederos / 20 días no perecederos)."
            ),
        })

    return contrato_principal, [c.id_contrato for c in contratos_aplicables], {
        'periodicidad_perecederos': per_per,
        'dias_perecederos': dias_per,
        'periodicidad_no_perecederos': per_no_per,
        'dias_no_perecederos': dias_no_per,
    }, faltantes


def _resolver_cupos_sede(
    sede: Sede,
    id_jornada=None,
    id_grado_filtro=None,
    id_grupo_filtro=None,
    contrato: Contrato | None = None,
):
    """
    Consulta los cupos proyectados por sede/jornada/grado y construye la lista de unidades de cálculo.
    """
    sj_qs = (
        SedeJornada.objects.filter(id_sede=sede)
        .select_related('id_jornada')
        .prefetch_related('grados_atendidos__id_grado__id_grupo_gramaje')
        .order_by('id_sede_jornada')
    )
    if id_jornada:
        sj_qs = sj_qs.filter(id_jornada_id=id_jornada)

    detalle_jornadas = []
    asignaciones = []
    resumen_grados_map = {}
    faltantes = []
    total_cupos = 0

    for sj in sj_qs:
        nombre_j = sj.id_jornada.nombre_jornada if sj.id_jornada else f"Jornada #{sj.id_jornada_id}"
        grados_activos = [
            g for g in sj.grados_atendidos.all()
            if (g.estado or '').upper() == 'ACTIVO'
        ]
        if id_grado_filtro:
            grados_activos = [g for g in grados_activos if g.id_grado_id == int(id_grado_filtro)]
        if id_grupo_filtro:
            grados_activos = [
                g for g in grados_activos
                if g.id_grado and g.id_grado.id_grupo_gramaje_id == int(id_grupo_filtro)
            ]

        cupos_j = int(sj.cupos or 0)
        suma_grados_j = sum(int(g.cupos or 0) for g in grados_activos)

        grados_serializados = []
        if grados_activos:
            cupos_efectivos_j = suma_grados_j
            total_cupos += cupos_efectivos_j

            if cupos_j > 0 and suma_grados_j != cupos_j and not id_grado_filtro and not id_grupo_filtro:
                faltantes.append({
                    'tipo': 'CUPOS_GRADO',
                    'nivel': 'ADVERTENCIA',
                    'id_jornada': sj.id_jornada_id,
                    'nombre_jornada': nombre_j,
                    'mensaje': (
                        f"En jornada '{nombre_j}', la suma de cupos por grado ({suma_grados_j}) "
                        f"difiere de los cupos totales de la jornada ({cupos_j})."
                    ),
                })

            for sg in grados_activos:
                grado = sg.id_grado
                grupo = getattr(grado, 'id_grupo_gramaje', None) if grado else None
                cupos_g = int(sg.cupos or 0)
                if cupos_g == 0:
                    faltantes.append({
                        'tipo': 'CUPOS',
                        'nivel': 'ADVERTENCIA',
                        'id_grado': sg.id_grado_id,
                        'nombre_grado': grado.nombre_grado if grado else '',
                        'mensaje': (
                            f"El grado '{grado.nombre_grado if grado else sg.id_grado_id}' en jornada "
                            f"'{nombre_j}' tiene 0 cupos proyectados."
                        ),
                    })
                item_g = {
                    'id_sede_jornada': sj.id_sede_jornada,
                    'id_jornada': sj.id_jornada_id,
                    'nombre_jornada': nombre_j,
                    'id_grado': sg.id_grado_id,
                    'nombre_grado': grado.nombre_grado if grado else f"Grado #{sg.id_grado_id}",
                    'nivel_educativo': grado.nivel_educativo if grado else None,
                    'id_grupo_gramaje': grupo.pk if grupo else None,
                    'nombre_grupo_gramaje': grupo.nombre if grupo else None,
                    'cupos': cupos_g,
                    'es_general': False,
                }
                grados_serializados.append(item_g)
                if cupos_g > 0:
                    asignaciones.append(item_g)
                    resumen_grados_map.setdefault(sg.id_grado_id, {
                        'id_grado': sg.id_grado_id,
                        'nombre_grado': item_g['nombre_grado'],
                        'nivel_educativo': item_g['nivel_educativo'],
                        'nombre_grupo_gramaje': item_g['nombre_grupo_gramaje'],
                        'cupos': 0,
                    })
                    resumen_grados_map[sg.id_grado_id]['cupos'] += cupos_g
        else:
            # Jornada sin segmentación por grados aún: usar cupos generales de SedeJornada
            total_cupos += cupos_j
            if cupos_j > 0:
                faltantes.append({
                    'tipo': 'CUPOS_GRADO',
                    'nivel': 'ADVERTENCIA',
                    'id_jornada': sj.id_jornada_id,
                    'nombre_jornada': nombre_j,
                    'mensaje': (
                        f"La jornada '{nombre_j}' tiene {cupos_j} cupos sin desglose por grado escolar; "
                        "se usará gramaje general cuando exista."
                    ),
                })
                asignaciones.append({
                    'id_sede_jornada': sj.id_sede_jornada,
                    'id_jornada': sj.id_jornada_id,
                    'nombre_jornada': nombre_j,
                    'id_grado': None,
                    'nombre_grado': 'General (sin desglose por grado)',
                    'nivel_educativo': None,
                    'id_grupo_gramaje': None,
                    'nombre_grupo_gramaje': None,
                    'cupos': cupos_j,
                    'es_general': True,
                })
            else:
                faltantes.append({
                    'tipo': 'CUPOS',
                    'nivel': 'ERROR',
                    'id_jornada': sj.id_jornada_id,
                    'nombre_jornada': nombre_j,
                    'mensaje': f"La jornada '{nombre_j}' no tiene cupos configurados.",
                })

        detalle_jornadas.append({
            'id_sede_jornada': sj.id_sede_jornada,
            'id_jornada': sj.id_jornada_id,
            'nombre_jornada': nombre_j,
            'cupos': suma_grados_j if grados_activos else cupos_j,
            'grados': grados_serializados,
        })

    if not sj_qs.exists():
        cupos_contrato = int(getattr(contrato, 'cupos', 0) or 0)
        faltantes.append({
            'tipo': 'CUPOS',
            'nivel': 'ERROR' if cupos_contrato == 0 else 'ADVERTENCIA',
            'mensaje': (
                f"La sede '{sede.nombre_sede}' no tiene jornadas ni cupos configurados en Sede-Jornada."
                + (f" (El contrato registra {cupos_contrato} cupos totales)." if cupos_contrato > 0 else "")
            ),
        })
        if cupos_contrato > 0:
            total_cupos = cupos_contrato
            asignaciones.append({
                'id_sede_jornada': None,
                'id_jornada': getattr(contrato, 'id_jornada_id', None),
                'nombre_jornada': getattr(getattr(contrato, 'id_jornada', None), 'nombre_jornada', 'Contrato') or 'Contrato',
                'id_grado': None,
                'nombre_grado': 'General (cupos de contrato)',
                'nivel_educativo': None,
                'id_grupo_gramaje': None,
                'nombre_grupo_gramaje': None,
                'cupos': cupos_contrato,
                'es_general': True,
            })

    return {
        'total_cupos': total_cupos,
        'detalle_jornadas': detalle_jornadas,
        'cupos_por_grado': list(resumen_grados_map.values()),
        'asignaciones': asignaciones,
        'faltantes': faltantes,
    }


def _resolver_productos_de_menus_y_recetas(
    sede: Sede,
    contrato_ids: list[int],
    id_jornada=None,
):
    """
    Consulta menús programados y recetas (Menu -> DetallePlato -> Plato -> RecetaComponente)
    respetando los IntegerFields heredados id_contrato e id_menu.
    """
    faltantes = []
    ingredientes_map = {}
    recetas_por_ingrediente = defaultdict(list)

    if not contrato_ids:
        return {
            'ingredientes': [],
            'recetas_por_ingrediente': recetas_por_ingrediente,
            'origen_productos': 'CATALOGO_GRAMAJES',
            'total_menus': 0,
            'faltantes': [{
                'tipo': 'MENUS',
                'nivel': 'ADVERTENCIA',
                'mensaje': f"No existen contratos ni menús programados para la sede '{sede.nombre_sede}'.",
            }],
        }

    menus_qs = Menu.objects.filter(id_contrato__in=contrato_ids).exclude(
        estado__iregex=r'^(anulado|cancelado|inactivo)$'
    )
    if id_jornada:
        menus_qs = menus_qs.filter(id_jornada_id=id_jornada)

    menu_ids = list(menus_qs.values_list('id_menu', flat=True))
    if not menu_ids:
        faltantes.append({
            'tipo': 'MENUS',
            'nivel': 'ADVERTENCIA',
            'mensaje': (
                f"Los contratos vinculados a la sede '{sede.nombre_sede}' no tienen menús programados; "
                "se evalúa el catálogo activo de gramajes."
            ),
        })
        return {
            'ingredientes': [],
            'recetas_por_ingrediente': recetas_por_ingrediente,
            'origen_productos': 'CATALOGO_GRAMAJES',
            'total_menus': 0,
            'faltantes': faltantes,
        }

    detalles = list(
        DetallePlato.objects.filter(id_menu__in=menu_ids, id_plato__isnull=False)
        .select_related('id_plato')
    )
    if not detalles:
        faltantes.append({
            'tipo': 'PLATOS_MENU',
            'nivel': 'ADVERTENCIA',
            'mensaje': "Los menús programados no tienen platos asignados en su configuración.",
        })
        return {
            'ingredientes': [],
            'recetas_por_ingrediente': recetas_por_ingrediente,
            'origen_productos': 'CATALOGO_GRAMAJES',
            'total_menus': len(menu_ids),
            'faltantes': faltantes,
        }

    platos_ids = list({d.id_plato_id for d in detalles if d.id_plato_id})
    platos_con_receta = set()
    componentes = list(
        RecetaComponente.objects.filter(id_plato_id__in=platos_ids, id_ingrediente__isnull=False)
        .select_related(
            'id_plato',
            'id_ingrediente',
            'id_ingrediente__id_unidad_medida',
            'id_ingrediente__id_tipo_mercado',
            'id_ingrediente__id_categoria_inventario',
        )
    )

    for comp in componentes:
        platos_con_receta.add(comp.id_plato_id)
        ing = comp.id_ingrediente
        if not ing:
            continue
        ingredientes_map[ing.id_ingrediente] = ing
        nombre_plato = getattr(comp.id_plato, 'nombre_plato', f"Plato #{comp.id_plato_id}")
        if nombre_plato not in recetas_por_ingrediente[ing.id_ingrediente]:
            recetas_por_ingrediente[ing.id_ingrediente].append(nombre_plato)

    platos_sin_receta = [
        getattr(d.id_plato, 'nombre_plato', f"Plato #{d.id_plato_id}")
        for d in detalles
        if d.id_plato_id and d.id_plato_id not in platos_con_receta
    ]
    if platos_sin_receta:
        nombres_unicos = ', '.join(sorted(set(platos_sin_receta))[:5])
        faltantes.append({
            'tipo': 'RECETAS',
            'nivel': 'ADVERTENCIA',
            'mensaje': f"Platos sin receta/ingredientes configurados en menús: {nombres_unicos}.",
        })

    if not ingredientes_map:
        faltantes.append({
            'tipo': 'RECETAS',
            'nivel': 'ADVERTENCIA',
            'mensaje': (
                "Los platos de los menús programados aún no tienen componentes de receta registrados; "
                "se evalúa el catálogo activo de gramajes."
            ),
        })
        return {
            'ingredientes': [],
            'recetas_por_ingrediente': recetas_por_ingrediente,
            'origen_productos': 'CATALOGO_GRAMAJES',
            'total_menus': len(menu_ids),
            'faltantes': faltantes,
        }

    return {
        'ingredientes': list(ingredientes_map.values()),
        'recetas_por_ingrediente': recetas_por_ingrediente,
        'origen_productos': 'MENUS_RECETAS',
        'total_menus': len(menu_ids),
        'faltantes': faltantes,
    }


def calcular_abastecimiento_sede(
    sede: Sede,
    *,
    dias_override=None,
    dias_perecederos_override=None,
    dias_no_perecederos_override=None,
    id_jornada=None,
    id_contrato=None,
    id_grado_filtro=None,
    id_grupo_filtro=None,
    fecha_referencia=None,
    incluir_todos_gramajes=False,
) -> dict:
    """
    Calcula automáticamente los requerimientos de abastecimiento por sede, jornada, grado,
    gramaje vigente, menús/recetas, periodicidad contractual y cruce con inventario central/sede.
    No modifica ninguna existencia de inventario.
    """
    contrato, contratos_ids, periodicidad_info, faltantes = _resolver_contrato_y_periodicidad(
        sede, id_contrato=id_contrato, id_jornada=id_jornada
    )

    dias_per = (
        int(dias_perecederos_override)
        if dias_perecederos_override is not None
        else (int(dias_override) if dias_override is not None else periodicidad_info['dias_perecederos'])
    )
    dias_no_per = (
        int(dias_no_perecederos_override)
        if dias_no_perecederos_override is not None
        else (int(dias_override) if dias_override is not None else periodicidad_info['dias_no_perecederos'])
    )
    dias_per = max(1, dias_per)
    dias_no_per = max(1, dias_no_per)

    cupos_info = _resolver_cupos_sede(
        sede,
        id_jornada=id_jornada,
        id_grado_filtro=id_grado_filtro,
        id_grupo_filtro=id_grupo_filtro,
        contrato=contrato,
    )
    faltantes.extend(cupos_info['faltantes'])

    menu_info = _resolver_productos_de_menus_y_recetas(
        sede, contratos_ids, id_jornada=id_jornada
    )
    faltantes.extend(menu_info['faltantes'])

    # Indexar gramajes activos por (id_ingrediente, id_grado)
    gramajes_qs = Gramage.objects.filter(estado='ACTIVO').select_related(
        'id_ingrediente',
        'id_ingrediente__id_unidad_medida',
        'id_ingrediente__id_tipo_mercado',
        'id_ingrediente__id_categoria_inventario',
        'id_unidad_medida',
        'id_grado',
        'id_grado__id_grupo_gramaje',
    ).order_by('-id_gramaje')

    if id_grado_filtro:
        gramajes_qs = gramajes_qs.filter(id_grado_id=id_grado_filtro)
    if id_grupo_filtro:
        gramajes_qs = gramajes_qs.filter(id_grado__id_grupo_gramaje_id=id_grupo_filtro)

    gramajes_exactos = {}
    primer_gramaje_por_ing = {}
    ingredientes_catalogados = {}

    for g in gramajes_qs:
        if not g.id_ingrediente:
            continue
        ing = g.id_ingrediente
        ing_id = ing.id_ingrediente
        ingredientes_catalogados[ing_id] = ing
        clave = (ing_id, g.id_grado_id)
        if clave not in gramajes_exactos:
            gramajes_exactos[clave] = g
        if ing_id not in primer_gramaje_por_ing:
            primer_gramaje_por_ing[ing_id] = g

    ingredientes_objetivo = {}
    for ing in menu_info['ingredientes']:
        ingredientes_objetivo[ing.id_ingrediente] = ing

    if menu_info['origen_productos'] == 'CATALOGO_GRAMAJES' or incluir_todos_gramajes or not ingredientes_objetivo:
        for ing_id, ing in ingredientes_catalogados.items():
            ingredientes_objetivo.setdefault(ing_id, ing)

    # Existencias de bodega central y de la sede (consulta de solo lectura)
    inv_central_map = {
        ic.id_ingrediente_id: Decimal(str(ic.cantidad_disponible or '0.000'))
        for ic in InventarioCentral.objects.all()
    }
    inv_sede_map = defaultdict(Decimal)
    for inv in Inventario.objects.filter(id_sede=sede):
        inv_sede_map[inv.id_ingrediente] += Decimal(str(inv.cantidad_actual or '0.000'))

    tipos_mercado_map = {}
    for tm in TipoMercado.objects.all():
        nombre_tm = (tm.nombre_tipo or '').lower()
        if 'pereced' in nombre_tm and 'no' not in nombre_tm:
            tipos_mercado_map['perecedero'] = tm.id_tipo_mercado
        elif 'no' in nombre_tm or 'grano' in nombre_tm:
            tipos_mercado_map['no_perecedero'] = tm.id_tipo_mercado

    sugerencias = []
    detalle_por_grado_global = []
    alertas_conversion = []
    total_cupos = cupos_info['total_cupos']
    asignaciones = cupos_info['asignaciones']

    total_items_perecederos = 0
    total_items_no_perecederos = 0

    for ing_id in sorted(
        ingredientes_objetivo.keys(),
        key=lambda k: (ingredientes_objetivo[k].nombre_ingrediente or '').lower(),
    ):
        ing = ingredientes_objetivo[ing_id]
        es_perecedero = _es_ingrediente_perecedero(ing)
        if es_perecedero:
            total_items_perecederos += 1
            dias_producto = dias_per
            periodicidad_aplicada = periodicidad_info['periodicidad_perecederos']
        else:
            total_items_no_perecederos += 1
            dias_producto = dias_no_per
            periodicidad_aplicada = periodicidad_info['periodicidad_no_perecederos']

        primer_g = primer_gramaje_por_ing.get(ing_id)
        unidad_destino = getattr(ing, 'id_unidad_medida', None) or (
            getattr(primer_g, 'id_unidad_medida', None) if primer_g else None
        )
        abrev_destino = _nombre_unidad(unidad_destino)
        nom_u = getattr(unidad_destino, 'nombre', abrev_destino) if unidad_destino else ''

        total_requerido = Decimal('0.000')
        cupos_cubiertos = 0
        detalle_grados_item = []
        errores_conversion_item = []
        grados_sin_gramaje = []
        gramaje_ref_original = None
        gramaje_ref_convertida = None
        primer_grado_info = None

        if not asignaciones:
            g_fallback = gramajes_exactos.get((ing_id, None)) or primer_g
            if g_fallback is None:
                faltantes.append({
                    'tipo': 'GRAMAJES',
                    'nivel': 'ERROR',
                    'id_ingrediente': ing_id,
                    'nombre_ingrediente': ing.nombre_ingrediente,
                    'mensaje': f"El producto '{ing.nombre_ingrediente}' no tiene gramaje activo configurado.",
                })
        else:
            for asig in asignaciones:
                grado_id = asig['id_grado']
                cupos_asig = int(asig['cupos'] or 0)
                if grado_id is not None:
                    gramaje = gramajes_exactos.get((ing_id, grado_id))
                else:
                    gramaje = gramajes_exactos.get((ing_id, None)) or primer_g

                if gramaje is None:
                    grados_sin_gramaje.append(asig['nombre_grado'])
                    mensaje_g = (
                        f"Falta gramaje activo para '{ing.nombre_ingrediente}' "
                        f"en grado '{asig['nombre_grado']}' ({asig['nombre_jornada']})."
                    )
                    fila_sin = {
                        'id_ingrediente': ing_id,
                        'nombre_ingrediente': ing.nombre_ingrediente,
                        'id_sede_jornada': asig['id_sede_jornada'],
                        'id_jornada': asig['id_jornada'],
                        'nombre_jornada': asig['nombre_jornada'],
                        'id_grado': grado_id,
                        'nombre_grado': asig['nombre_grado'],
                        'nivel_educativo': asig['nivel_educativo'],
                        'nombre_grupo_gramaje': asig['nombre_grupo_gramaje'],
                        'cupos_utilizados': cupos_asig,
                        'id_gramaje': None,
                        'gramaje_original': None,
                        'unidad_gramaje': '',
                        'gramaje_convertido': None,
                        'unidad_destino': abrev_destino or nom_u,
                        'dias_periodo': dias_producto,
                        'cantidad_requerida': 0.0,
                        'estado': 'SIN_GRAMAJE',
                        'mensaje_alerta': mensaje_g,
                    }
                    detalle_grados_item.append(fila_sin)
                    detalle_por_grado_global.append(fila_sin)
                    faltantes.append({
                        'tipo': 'GRAMAJES',
                        'nivel': 'ERROR',
                        'id_ingrediente': ing_id,
                        'nombre_ingrediente': ing.nombre_ingrediente,
                        'id_grado': grado_id,
                        'nombre_grado': asig['nombre_grado'],
                        'mensaje': mensaje_g,
                    })
                    continue

                if primer_grado_info is None:
                    primer_grado_info = gramaje

                cant_orig = Decimal(str(gramaje.cantidad_gramaje or '0.000'))
                unidad_g = gramaje.id_unidad_medida
                cant_conv = cant_orig
                error_conv_msg = None

                if unidad_g is not None and unidad_destino is not None:
                    try:
                        cant_conv = convertir_cantidad(
                            cant_orig, unidad_g, unidad_destino, ingrediente=ing
                        )
                    except ErrorConversionUnidad as exc:
                        error_conv_msg = str(exc)

                if error_conv_msg:
                    errores_conversion_item.append(error_conv_msg)
                    alertas_conversion.append({
                        'id_ingrediente': ing_id,
                        'nombre_ingrediente': ing.nombre_ingrediente,
                        'id_grado': grado_id,
                        'nombre_grado': asig['nombre_grado'],
                        'mensaje': error_conv_msg,
                    })
                    faltantes.append({
                        'tipo': 'CONVERSION_UNIDAD',
                        'nivel': 'ERROR',
                        'id_ingrediente': ing_id,
                        'nombre_ingrediente': ing.nombre_ingrediente,
                        'id_grado': grado_id,
                        'nombre_grado': asig['nombre_grado'],
                        'mensaje': error_conv_msg,
                    })
                    fila_err = {
                        'id_ingrediente': ing_id,
                        'nombre_ingrediente': ing.nombre_ingrediente,
                        'id_sede_jornada': asig['id_sede_jornada'],
                        'id_jornada': asig['id_jornada'],
                        'nombre_jornada': asig['nombre_jornada'],
                        'id_grado': grado_id,
                        'nombre_grado': asig['nombre_grado'],
                        'nivel_educativo': asig['nivel_educativo'],
                        'nombre_grupo_gramaje': asig['nombre_grupo_gramaje'],
                        'cupos_utilizados': cupos_asig,
                        'id_gramaje': gramaje.id_gramaje,
                        'gramaje_original': float(cant_orig),
                        'unidad_gramaje': _nombre_unidad(unidad_g),
                        'gramaje_convertido': None,
                        'unidad_destino': abrev_destino or nom_u,
                        'dias_periodo': dias_producto,
                        'cantidad_requerida': 0.0,
                        'estado': 'ERROR_CONVERSION',
                        'mensaje_alerta': error_conv_msg,
                    }
                    detalle_grados_item.append(fila_err)
                    detalle_por_grado_global.append(fila_err)
                    continue

                if gramaje_ref_original is None:
                    gramaje_ref_original = cant_orig
                    gramaje_ref_convertida = cant_conv

                subtotal_grado = Decimal(cupos_asig) * cant_conv * Decimal(dias_producto)
                total_requerido += subtotal_grado
                cupos_cubiertos += cupos_asig

                fila_ok = {
                    'id_ingrediente': ing_id,
                    'nombre_ingrediente': ing.nombre_ingrediente,
                    'id_sede_jornada': asig['id_sede_jornada'],
                    'id_jornada': asig['id_jornada'],
                    'nombre_jornada': asig['nombre_jornada'],
                    'id_grado': grado_id,
                    'nombre_grado': asig['nombre_grado'],
                    'nivel_educativo': asig['nivel_educativo'],
                    'nombre_grupo_gramaje': asig['nombre_grupo_gramaje'],
                    'cupos_utilizados': cupos_asig,
                    'id_gramaje': gramaje.id_gramaje,
                    'gramaje_original': float(cant_orig),
                    'unidad_gramaje': _nombre_unidad(unidad_g),
                    'gramaje_convertido': float(round(cant_conv, 6)),
                    'unidad_destino': abrev_destino or nom_u,
                    'dias_periodo': dias_producto,
                    'cantidad_requerida': float(round(subtotal_grado, 3)),
                    'estado': 'CALCULADO',
                    'mensaje_alerta': None,
                }
                detalle_grados_item.append(fila_ok)
                detalle_por_grado_global.append(fila_ok)

        stock_sede = inv_sede_map.get(ing_id, Decimal('0.000'))
        stock_central = inv_central_map.get(ing_id, Decimal('0.000'))
        necesidad_neta = max(Decimal('0.000'), total_requerido - stock_sede)
        pendiente_abastecer = max(Decimal('0.000'), necesidad_neta - stock_central)

        if errores_conversion_item and total_requerido == 0:
            estado_bodega = 'ERROR_CONVERSION'
        else:
            estado_bodega = 'SUFICIENTE' if stock_central >= necesidad_neta else 'INSUFICIENTE'

        presentacion_requerida = formatear_cantidad_apropiada(total_requerido, unidad_destino)
        presentacion_sugerida = formatear_cantidad_apropiada(necesidad_neta, unidad_destino)
        grupo_obj = primer_grado_info.id_grado.id_grupo_gramaje if (primer_grado_info and primer_grado_info.id_grado_id) else None

        id_tm_item = ing.id_tipo_mercado_id or tipos_mercado_map.get(
            'perecedero' if es_perecedero else 'no_perecedero'
        )

        sugerencias.append({
            'id_ingrediente': ing_id,
            'nombre_ingrediente': ing.nombre_ingrediente,
            'id_tipo_mercado': id_tm_item,
            'tipo_conservacion': 'perecedero' if es_perecedero else 'no_perecedero',
            'es_perecedero': es_perecedero,
            'clasificacion_tipo': 'Perecedero' if es_perecedero else 'No perecedero',
            'periodicidad_aplicada': periodicidad_aplicada,
            'dias_periodo': dias_producto,
            'unidad_medida': nom_u,
            'unidad_abreviatura': abrev_destino or nom_u,
            'cupos_totales_utilizados': cupos_cubiertos,
            'porcion_gramaje': float(gramaje_ref_original or 0),
            'porcion_gramaje_convertida': (
                float(round(gramaje_ref_convertida, 6)) if gramaje_ref_convertida is not None else None
            ),
            'consumo_teorico_periodo': float(round(total_requerido, 3)),
            'cantidad_total_requerida': float(round(total_requerido, 3)),
            'presentacion_consumo': presentacion_requerida,
            'presentacion_requerida': presentacion_requerida,
            'stock_actual_sede': float(round(stock_sede, 3)),
            'cantidad_sugerida_despacho': float(round(necesidad_neta, 3)),
            'necesidad_neta_sede': float(round(necesidad_neta, 3)),
            'presentacion_sugerida': presentacion_sugerida,
            'stock_bodega_central': float(round(stock_central, 3)),
            'estado_bodega_central': estado_bodega,
            'pendiente_abastecer': float(round(pendiente_abastecer, 3)),
            'faltante_bodega_central': float(round(pendiente_abastecer, 3)),
            'error_conversion': bool(errores_conversion_item),
            'alerta_conversion': '; '.join(errores_conversion_item) if errores_conversion_item else None,
            'tiene_gramajes_faltantes': bool(grados_sin_gramaje),
            'grados_sin_gramaje': grados_sin_gramaje,
            'platos_relacionados': menu_info['recetas_por_ingrediente'].get(ing_id, []),
            'detalle_por_grado': detalle_grados_item,
            'id_grado': primer_grado_info.id_grado_id if primer_grado_info else None,
            'nombre_grado': (
                primer_grado_info.id_grado.nombre_grado
                if (primer_grado_info and primer_grado_info.id_grado_id)
                else None
            ),
            'id_grupo_gramaje': grupo_obj.pk if grupo_obj else None,
            'nombre_grupo_gramaje': grupo_obj.nombre if grupo_obj else None,
            'nivel_educativo': (
                primer_grado_info.id_grado.nivel_educativo
                if (primer_grado_info and primer_grado_info.id_grado_id)
                else None
            ),
        })

    nom_inst = sede.id_institucion.nombre_institucion if sede.id_institucion else 'Sin institucion'
    contrato_data = None
    if contrato:
        contrato_data = {
            'id_contrato': contrato.id_contrato,
            'numero_cor': contrato.numero_cor,
            'estado': contrato.estado,
            'fecha_inicio': str(contrato.fecha_inicio) if contrato.fecha_inicio else None,
            'fecha_fin': str(contrato.fecha_fin) if contrato.fecha_fin else None,
            'cupos': contrato.cupos,
            'periodicidad_perecederos': contrato.periodicidad_perecederos,
            'dias_cobertura_perecederos': dias_per,
            'periodicidad_no_perecederos': contrato.periodicidad_no_perecederos,
            'dias_cobertura_no_perecederos': dias_no_per,
        }

    # Deduplicar alertas por (tipo, mensaje)
    faltantes_unicos = []
    vistas = set()
    for f in faltantes:
        clave = (f.get('tipo'), f.get('mensaje'))
        if clave not in vistas:
            vistas.add(clave)
            faltantes_unicos.append(f)

    dias_calculados_compat = int(dias_override) if dias_override is not None else dias_no_per

    return {
        'id_institucion': sede.id_institucion_id,
        'id_sede': sede.id_sede,
        'nombre_sede': sede.nombre_sede,
        'institucion': nom_inst,
        'contrato': contrato_data,
        'periodicidad': {
            'periodicidad_perecederos': periodicidad_info['periodicidad_perecederos'],
            'dias_perecederos': dias_per,
            'periodicidad_no_perecederos': periodicidad_info['periodicidad_no_perecederos'],
            'dias_no_perecederos': dias_no_per,
        },
        'total_cupos': total_cupos,
        'jornadas': cupos_info['detalle_jornadas'],
        'cupos_por_grado': cupos_info['cupos_por_grado'],
        'dias_calculados': dias_calculados_compat,
        'origen_productos': menu_info['origen_productos'],
        'total_menus_programados': menu_info['total_menus'],
        'resumen_tipos': {
            'total_productos': len(sugerencias),
            'perecederos': total_items_perecederos,
            'no_perecederos': total_items_no_perecederos,
            'insuficientes_bodega': sum(
                1 for s in sugerencias if s['estado_bodega_central'] == 'INSUFICIENTE'
            ),
        },
        'impacta_inventario': False,
        'fecha_calculo': timezone.now().isoformat(),
        'alertas_conversion': alertas_conversion,
        'faltantes_configuracion': faltantes_unicos,
        'productos_sugeridos': sugerencias,
        'detalle_por_grado_global': detalle_por_grado_global,
    }


def _es_verdadero(valor) -> bool:
    if isinstance(valor, bool):
        return valor
    if isinstance(valor, (int, float)):
        return valor != 0
    if isinstance(valor, str):
        return valor.strip().lower() in ('1', 'true', 'si', 'sí', 'yes')
    return False


def _generar_codigo_documento(sede_id: int) -> str:
    fecha_txt = date.today().strftime('%Y%m%d')
    sufijo = uuid.uuid4().hex[:6].upper()
    return f"ENT-{fecha_txt}-S{sede_id}-{sufijo}"


def _resolver_tipo_mercado_por_ingrediente(ing_id: int, tipo_mercado_defecto=None):
    ing = Ingrediente.objects.filter(pk=ing_id).select_related('id_tipo_mercado', 'id_categoria_inventario').first()
    if ing and ing.id_tipo_mercado_id:
        return ing.id_tipo_mercado_id
    if tipo_mercado_defecto:
        return tipo_mercado_defecto
    if ing:
        es_per = _es_ingrediente_perecedero(ing)
        if es_per:
            tm = TipoMercado.objects.filter(nombre_tipo__icontains='pereced').exclude(nombre_tipo__icontains='no').first()
        else:
            tm = TipoMercado.objects.filter(nombre_tipo__icontains='no').first() or TipoMercado.objects.filter(
                nombre_tipo__icontains='grano'
            ).first()
        if tm:
            return tm.id_tipo_mercado
    return TipoMercado.objects.values_list('id_tipo_mercado', flat=True).first()


def _evaluar_contexto_y_items(usuario, sede: Sede, items: list[dict], data: dict, fallback_fecha: str):
    """
    Ejecuta el cálculo vigente de la sede y valida que ningún ítem exceda la cantidad requerida
    sin autorización explícita y justificación. Retorna metadatos listos para persistir entrega y snapshot.
    """
    validar_alcance_sedes(usuario, Sede.objects.filter(pk=sede.pk), id_institucion=sede.id_institucion_id)

    calculo = calcular_abastecimiento_sede(
        sede,
        dias_override=data.get('dias'),
        dias_perecederos_override=data.get('dias_perecederos'),
        dias_no_perecederos_override=data.get('dias_no_perecederos'),
        id_jornada=data.get('id_jornada'),
        id_contrato=data.get('id_contrato'),
        incluir_todos_gramajes=_es_verdadero(data.get('incluir_todos_gramajes')),
    )

    sede_tiene_parametrizacion = bool(
        calculo['total_cupos'] > 0
        or calculo['contrato'] is not None
        or calculo['productos_sugeridos']
        or _es_verdadero(data.get('validar_contra_calculo'))
    )

    mapa_calculado = {int(p['id_ingrediente']): p for p in calculo['productos_sugeridos']}

    autorizacion_exceso = _es_verdadero(
        data.get('autorizacion_exceso') if 'autorizacion_exceso' in data else data.get('autorizar_exceso')
    )
    autorizado_por = str(data.get('autorizado_por') or '').strip()
    justificacion_exceso = str(data.get('justificacion_exceso') or '').strip()

    if _es_usuario_bd(usuario) and hasattr(usuario, 'es_superadmin') and usuario.es_superadmin():
        if autorizacion_exceso and not autorizado_por:
            autorizado_por = f"{usuario.nombre} {usuario.apellido}".strip() or usuario.correo

    id_tipo_mercado_global = data.get('id_tipo_mercado')
    fecha_venc_global = data.get('fecha_vencimiento') or fallback_fecha

    excedidos = []
    items_preparados = []

    for item in items:
        id_ing = item.get('id_ingrediente')
        cant = item.get('cantidad')
        unidad = item.get('unidad', '')
        if not id_ing or cant is None:
            continue

        try:
            id_ing_int = int(id_ing)
            cant_dec = Decimal(str(cant))
        except Exception:
            raise ValidationError({'error': f'Cantidad inválida para el ingrediente {id_ing}.'})

        if not cant_dec.is_finite() or cant_dec <= 0:
            raise ValidationError({
                'error': f'La cantidad del ingrediente {id_ing} debe ser mayor que cero.'
            })

        prod_calc = mapa_calculado.get(id_ing_int)
        if prod_calc is not None:
            requerido_neto = Decimal(str(prod_calc['cantidad_sugerida_despacho']))
            requerido_total = Decimal(str(prod_calc['cantidad_total_requerida']))
            nombre_ing = prod_calc['nombre_ingrediente']
            id_tm_item = (
                item.get('id_tipo_mercado')
                or prod_calc.get('id_tipo_mercado')
                or id_tipo_mercado_global
                or _resolver_tipo_mercado_por_ingrediente(id_ing_int)
            )
        else:
            requerido_neto = Decimal('0.000')
            requerido_total = Decimal('0.000')
            nombre_ing = Ingrediente.objects.filter(pk=id_ing_int).values_list(
                'nombre_ingrediente', flat=True
            ).first() or f"Ingrediente #{id_ing_int}"
            id_tm_item = (
                item.get('id_tipo_mercado')
                or id_tipo_mercado_global
                or _resolver_tipo_mercado_por_ingrediente(id_ing_int)
            )

        if not id_tm_item:
            raise ValidationError({
                'error': f"No se encontró un tipo de mercado válido para el ingrediente '{nombre_ing}'."
            })

        supera = False
        if sede_tiene_parametrizacion and cant_dec > (requerido_neto + TOLERANCIA_EXCESO):
            supera = True
            excedidos.append({
                'id_ingrediente': id_ing_int,
                'nombre_ingrediente': nombre_ing,
                'cantidad_solicitada': float(cant_dec),
                'cantidad_calculada_neta': float(requerido_neto),
                'cantidad_calculada_total': float(requerido_total),
                'exceso': float(round(cant_dec - requerido_neto, 3)),
            })

        items_preparados.append({
            'id_ingrediente': id_ing_int,
            'nombre_ingrediente': nombre_ing,
            'cantidad': cant_dec,
            'unidad': unidad,
            'id_tipo_mercado': id_tm_item,
            'fecha_vencimiento': item.get('fecha_vencimiento') or fecha_venc_global,
            'requerido_neto': requerido_neto,
            'requerido_total': requerido_total,
            'supera': supera,
        })

    if not items_preparados:
        raise ValidationError({'error': "Debe incluir al menos un producto válido en la lista 'items'."})

    if excedidos and (not autorizacion_exceso or not autorizado_por or len(justificacion_exceso) < 5):
        raise ValidationError({
            'error': (
                'No se permite despachar cantidades superiores a las requeridas por el cálculo '
                'sin autorización expresa (autorizado_por) y justificación detallada.'
            ),
            'requiere_autorizacion_exceso': True,
            'excedidos': excedidos,
        })

    return {
        'calculo': calculo,
        'sede_tiene_parametrizacion': sede_tiene_parametrizacion,
        'items_preparados': items_preparados,
        'excedidos': excedidos,
        'autorizacion_exceso': bool(excedidos and autorizacion_exceso),
        'autorizado_por': autorizado_por if excedidos else '',
        'justificacion_exceso': justificacion_exceso if excedidos else '',
    }


def _crear_snapshot_calculo(sede: Sede, usuario, data: dict, eval_ctx: dict, fallback_fecha: str) -> CalculoEntrega:
    calculo = eval_ctx['calculo']
    codigo_documento = str(data.get('codigo_documento') or '').strip() or _generar_codigo_documento(sede.id_sede)
    user_id = getattr(usuario, 'id_usuario', None) or 1
    supervisor_nombre = str(data.get('supervisor_nombre') or '').strip()
    if not supervisor_nombre and _es_usuario_bd(usuario):
        supervisor_nombre = f"{getattr(usuario, 'nombre', '')} {getattr(usuario, 'apellido', '')}".strip()

    contrato_id_val = calculo['contrato']['id_contrato'] if calculo.get('contrato') else data.get('id_contrato')
    periodo_desc = (
        str(data.get('periodo_descripcion') or '').strip()
        or (
            f"Perecederos: {calculo['periodicidad']['dias_perecederos']} días · "
            f"No perecederos: {calculo['periodicidad']['dias_no_perecederos']} días"
        )
    )
    cantidades_despachadas = {
        item['id_ingrediente']: float(item['cantidad'])
        for item in eval_ctx['items_preparados']
    }
    consolidado_con_despacho = []
    for p in calculo['productos_sugeridos']:
        copia = dict(p)
        copia['cantidad_despachada'] = cantidades_despachadas.get(int(p['id_ingrediente']), 0.0)
        copia['supera_calculo'] = any(
            e['id_ingrediente'] == int(p['id_ingrediente']) for e in eval_ctx['excedidos']
        )
        consolidado_con_despacho.append(copia)

    return CalculoEntrega.objects.create(
        codigo_documento=codigo_documento,
        id_institucion=sede.id_institucion,
        id_sede=sede,
        id_contrato_id=contrato_id_val,
        id_jornada_id=data.get('id_jornada') or None,
        id_usuario_supervisor=user_id,
        supervisor_nombre=supervisor_nombre,
        fecha_referencia=data.get('fecha_referencia') or fallback_fecha,
        periodo_inicio=data.get('periodo_inicio') or fallback_fecha,
        periodo_fin=data.get('periodo_fin') or None,
        periodo_descripcion=periodo_desc,
        dias_perecederos=calculo['periodicidad']['dias_perecederos'],
        dias_no_perecederos=calculo['periodicidad']['dias_no_perecederos'],
        total_cupos=calculo['total_cupos'],
        autorizacion_exceso=eval_ctx['autorizacion_exceso'],
        autorizado_por=eval_ctx['autorizado_por'],
        justificacion_exceso=eval_ctx['justificacion_exceso'],
        parametros_snapshot={
            'institucion': calculo['institucion'],
            'sede': calculo['nombre_sede'],
            'contrato': calculo['contrato'],
            'periodicidad': calculo['periodicidad'],
            'jornadas': calculo['jornadas'],
            'cupos_por_grado': calculo['cupos_por_grado'],
            'origen_productos': calculo['origen_productos'],
            'sin_calculo_parametrizado': not eval_ctx['sede_tiene_parametrizacion'],
        },
        consolidado_snapshot=consolidado_con_despacho,
        detalle_grados_snapshot=calculo['detalle_por_grado_global'],
        alertas_snapshot=calculo['faltantes_configuracion'],
    )


def validar_y_registrar_despacho_lote(usuario, data: dict) -> dict:
    """
    Valida reglas de alcance, cálculo vs cantidad despachada (bloqueando excesos sin autorización
    y justificación), crea las entregas y persiste el cálculo original como soporte auditable.
    """
    id_sede = data.get('id_sede')
    fecha_entrega = data.get('fecha_entrega')
    observaciones = data.get('observaciones', '')
    frecuencia = data.get('frecuencia', 'Quincenal')
    items = data.get('items', [])

    if not id_sede or not fecha_entrega:
        raise ValidationError({
            'error': "Los campos 'id_sede' y 'fecha_entrega' son obligatorios."
        })

    if not isinstance(items, list) or not items:
        raise ValidationError({
            'error': "Debe incluir al menos un producto en la lista 'items'."
        })

    sede = Sede.objects.filter(pk=id_sede).select_related('id_institucion').first()
    if not sede:
        raise LookupError(f"La sede con id {id_sede} no existe.")

    eval_ctx = _evaluar_contexto_y_items(usuario, sede, items, data, str(fecha_entrega))
    user_id = getattr(usuario, 'id_usuario', None) or 1
    calculo = eval_ctx['calculo']
    contrato_id_val = calculo['contrato']['id_contrato'] if calculo.get('contrato') else data.get('id_contrato')

    entregas_creadas = []
    with transaction.atomic():
        calculo_obj = _crear_snapshot_calculo(sede, usuario, data, eval_ctx, str(fecha_entrega))
        for item in eval_ctx['items_preparados']:
            entrega = Entrega.objects.create(
                id_institucion=sede.id_institucion,
                id_sede=sede,
                id_contrato_id=contrato_id_val,
                id_calculo_entrega=calculo_obj,
                documento_entrega=calculo_obj.codigo_documento,
                cantidad_requerida_calculo=(
                    item['requerido_neto'] if eval_ctx['sede_tiene_parametrizacion'] else None
                ),
                supera_calculo=item['supera'],
                autorizado_por=eval_ctx['autorizado_por'] if item['supera'] else '',
                justificacion_exceso=eval_ctx['justificacion_exceso'] if item['supera'] else '',
                id_ingrediente=item['id_ingrediente'],
                id_usuario_supervisor=user_id,
                id_tipo_mercado=item['id_tipo_mercado'],
                fecha_entrega=fecha_entrega,
                fecha_vencimiento=item['fecha_vencimiento'],
                cantidad=item['cantidad'],
                observaciones=observaciones,
                frecuencia=frecuencia,
                unidad=item['unidad'],
                estado='EN_TRANSITO',
            )
            entregas_creadas.append(entrega)

    return {
        'sede': sede,
        'calculo_obj': calculo_obj,
        'entregas_creadas': entregas_creadas,
    }


def preparar_entrega_individual(usuario, serializer, raw_data: dict) -> dict:
    """
    Valida alcance y exceso contra el cálculo cuando se crea una entrega individual asociada a sede,
    dejando el cálculo auditable persistido dentro de la transacción.
    """
    inst = serializer.validated_data.get('id_institucion')
    sede = serializer.validated_data.get('id_sede')
    if not inst and sede and getattr(sede, 'id_institucion', None):
        inst = sede.id_institucion

    if sede is None:
        if inst is not None:
            validar_alcance_sedes(usuario, Sede.objects.none(), id_institucion=inst.pk)
        return {'id_institucion': inst}

    item = {
        'id_ingrediente': serializer.validated_data.get('id_ingrediente'),
        'cantidad': serializer.validated_data.get('cantidad'),
        'unidad': serializer.validated_data.get('unidad', ''),
        'id_tipo_mercado': serializer.validated_data.get('id_tipo_mercado'),
        'fecha_vencimiento': serializer.validated_data.get('fecha_vencimiento'),
    }
    fecha_entrega = str(serializer.validated_data.get('fecha_entrega') or date.today())
    eval_ctx = _evaluar_contexto_y_items(usuario, sede, [item], raw_data, fecha_entrega)
    prep = eval_ctx['items_preparados'][0]
    calculo = eval_ctx['calculo']
    contrato_id_val = calculo['contrato']['id_contrato'] if calculo.get('contrato') else raw_data.get('id_contrato')

    return {
        'id_institucion': inst,
        'sede': sede,
        'eval_ctx': eval_ctx,
        'fallback_fecha': fecha_entrega,
        'extra_save_kwargs': {
            'id_contrato_id': contrato_id_val,
            'cantidad_requerida_calculo': prep['requerido_neto'] if eval_ctx['sede_tiene_parametrizacion'] else None,
            'supera_calculo': prep['supera'],
            'autorizado_por': eval_ctx['autorizado_por'] if prep['supera'] else '',
            'justificacion_exceso': eval_ctx['justificacion_exceso'] if prep['supera'] else '',
        },
    }
