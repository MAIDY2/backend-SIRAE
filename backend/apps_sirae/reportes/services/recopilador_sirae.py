from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal

from django.db import DatabaseError
from django.db.models import Q
from django.utils import timezone

from apps_sirae.asistencia_diaria.models import AsistenciaDiaria
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.detalle_plato.models import DetallePlato
from apps_sirae.entregas.models import CalculoEntrega, Entrega
from apps_sirae.entregas.services import calcular_abastecimiento_sede
from apps_sirae.entradas_inventario.models import EntradaInventario
from apps_sirae.gramage.models import Gramage
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.instituciones.models import Institucion, SupervisorInstitucion
from apps_sirae.inventario.models import Inventario
from apps_sirae.menus.models import Menu
from apps_sirae.preparacion_asignada.models import PreparacionAsignada
from apps_sirae.receta_componente.models import RecetaComponente
from apps_sirae.salidas_inventario.models import SalidaInventario
from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
from apps_sirae.sedes.models import Sede
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.usuarios.alcance import (
    obtener_instituciones_autorizadas,
    obtener_sede_jornadas_autorizadas,
    obtener_sedes_autorizadas,
)
from apps_sirae.usuarios.models import Usuario


def _to_float(valor, decimales=3) -> float:
    try:
        return round(float(valor or 0), decimales)
    except (TypeError, ValueError):
        return 0.0


def _iso(valor) -> str:
    if not valor:
        return ''
    if isinstance(valor, datetime):
        return valor.isoformat()
    if isinstance(valor, date):
        return valor.isoformat()
    return str(valor)


def _actualizar_max_fecha(actual, candidata):
    if not candidata:
        return actual
    if isinstance(candidata, date) and not isinstance(candidata, datetime):
        candidata = datetime.combine(candidata, datetime.min.time(), tzinfo=timezone.get_current_timezone())
    elif isinstance(candidata, datetime) and timezone.is_naive(candidata):
        candidata = timezone.make_aware(candidata, timezone.get_current_timezone())
    if actual is None or candidata > actual:
        return candidata
    return actual


def _resolver_alcance_filtrado(
    usuario,
    *,
    id_institucion=None,
    id_sede=None,
    id_jornada=None,
    id_contrato=None,
):
    inst_qs = obtener_instituciones_autorizadas(usuario)
    sede_qs = obtener_sedes_autorizadas(usuario).select_related('id_institucion')
    sj_qs = obtener_sede_jornadas_autorizadas(usuario).select_related('id_sede', 'id_sede__id_institucion', 'id_jornada')

    if id_institucion:
        inst_qs = inst_qs.filter(id_institucion=id_institucion)
        sede_qs = sede_qs.filter(id_institucion_id=id_institucion)
        sj_qs = sj_qs.filter(id_sede__id_institucion_id=id_institucion)
    if id_sede:
        sede_qs = sede_qs.filter(id_sede=id_sede)
        sj_qs = sj_qs.filter(id_sede_id=id_sede)
    if id_jornada:
        sj_qs = sj_qs.filter(id_jornada_id=id_jornada)

    if getattr(usuario, 'es_jefa_manipuladoras', lambda: False)():
        sedes_por_jornada = set(sj_qs.values_list('id_sede_id', flat=True))
        if sedes_por_jornada:
            sede_qs = sede_qs.filter(id_sede__in=sedes_por_jornada)
        elif getattr(usuario, 'id_sede_id', None):
            sede_qs = sede_qs.filter(id_sede=usuario.id_sede_id)

    instituciones = list(inst_qs.order_by('nombre_institucion', 'id_institucion'))
    sedes = list(sede_qs.order_by('nombre_sede', 'id_sede'))
    sedes_ids = [s.id_sede for s in sedes]
    inst_ids = [i.id_institucion for i in instituciones]

    contratos_qs = Contrato.objects.select_related(
        'id_institucion', 'id_sede', 'id_jornada', 'id_usuario_supervisor'
    )
    if sedes_ids or inst_ids:
        contratos_qs = contratos_qs.filter(
            Q(id_sede_id__in=sedes_ids) | Q(id_sede__isnull=True, id_institucion_id__in=inst_ids)
        )
    else:
        contratos_qs = contratos_qs.none()

    if id_contrato:
        contratos_qs = contratos_qs.filter(id_contrato=id_contrato)
    if id_jornada:
        contratos_qs = contratos_qs.filter(Q(id_jornada_id=id_jornada) | Q(id_jornada__isnull=True))

    contratos = list(contratos_qs.order_by('-fecha_inicio', '-id_contrato'))
    sede_jornadas = list(sj_qs.order_by('id_sede_id', 'id_jornada_id'))

    return {
        'instituciones': instituciones,
        'sedes': sedes,
        'sedes_ids': sedes_ids,
        'inst_ids': inst_ids,
        'contratos': contratos,
        'contrato_ids': [c.id_contrato for c in contratos],
        'sede_jornadas': sede_jornadas,
    }


def _resolver_responsables_reales(inst_ids: list[int], sedes_ids: list[int], contratos: list[Contrato]):
    """
    Obtiene nombres y cargos reales de Supervisor, Administrador Institucional y Jefa de Manipuladoras
    desde la base de datos (sin nombres ni firmas quemadas).
    """
    supervisores = []
    seen_sup = set()
    for sup_rel in SupervisorInstitucion.objects.filter(
        id_institucion_id__in=inst_ids,
        id_supervisor__is_active=True,
    ).select_related('id_supervisor'):
        u = sup_rel.id_supervisor
        if u and u.id_usuario not in seen_sup:
            seen_sup.add(u.id_usuario)
            supervisores.append({'id_usuario': u.id_usuario, 'nombre': u.nombre_completo, 'correo': u.correo})

    for c in contratos:
        u = getattr(c, 'id_usuario_supervisor', None)
        if u and u.id_usuario not in seen_sup:
            seen_sup.add(u.id_usuario)
            supervisores.append({'id_usuario': u.id_usuario, 'nombre': u.nombre_completo, 'correo': u.correo})

    administradores = []
    jefas_cocina = []
    usuarios_relacionados_ids = set(seen_sup)
    for u in Usuario.objects.filter(
        Q(id_sede_id__in=sedes_ids) | Q(id_institucion_id__in=inst_ids),
        is_active=True,
    ).select_related('rol'):
        usuarios_relacionados_ids.add(u.id_usuario)
        if u.es_administrador():
            administradores.append({'id_usuario': u.id_usuario, 'nombre': u.nombre_completo, 'correo': u.correo})
        elif u.es_jefa_manipuladoras():
            jefas_cocina.append({'id_usuario': u.id_usuario, 'nombre': u.nombre_completo, 'correo': u.correo})

    return {
        'supervisores': supervisores,
        'administradores': administradores,
        'jefas_cocina': jefas_cocina,
        'supervisor_nombre': supervisores[0]['nombre'] if supervisores else 'PENDIENTE',
        'administrador_nombre': administradores[0]['nombre'] if administradores else 'PENDIENTE',
        'jefa_cocina_nombre': jefas_cocina[0]['nombre'] if jefas_cocina else 'PENDIENTE',
        'usuarios_relacionados_ids': list(usuarios_relacionados_ids),
    }


def _resolver_cupos_y_niveles(sede_jornadas: list[SedeJornada], contratos: list[Contrato]):
    sj_ids = [sj.id_sede_jornada for sj in sede_jornadas]
    sj_map = {sj.id_sede_jornada: sj for sj in sede_jornadas}
    grados_atendidos = list(
        SedeJornadaGrado.objects.filter(
            id_sede_jornada_id__in=sj_ids,
            estado='ACTIVO',
        ).select_related('id_grado', 'id_grado__id_grupo_gramaje', 'id_sede_jornada__id_sede', 'id_sede_jornada__id_jornada')
    )

    por_nivel = defaultdict(int)
    detalle_grados = []
    cupos_por_sede = defaultdict(int)
    cupos_por_grado_id = defaultdict(int)

    for item in grados_atendidos:
        cup = int(item.cupos or 0)
        grado = item.id_grado
        sj = item.id_sede_jornada
        nivel = getattr(grado, 'nivel_educativo', None) or 'OTRO'
        por_nivel[nivel] += cup
        cupos_por_sede[sj.id_sede_id] += cup
        if item.id_grado_id:
            cupos_por_grado_id[item.id_grado_id] += cup
        detalle_grados.append({
            'id_sede': sj.id_sede_id,
            'nombre_sede': sj.id_sede.nombre_sede if sj.id_sede else '',
            'id_jornada': sj.id_jornada_id,
            'nombre_jornada': sj.id_jornada.nombre_jornada if sj.id_jornada else '',
            'id_grado': item.id_grado_id,
            'nombre_grado': grado.nombre_grado if grado else f'Grado {item.id_grado_id}',
            'nivel_educativo': nivel,
            'nombre_grupo_gramaje': grado.id_grupo_gramaje.nombre if (grado and grado.id_grupo_gramaje) else '',
            'cupos': cup,
        })

    # Fallback únicamente a cupos reales registrados en SedeJornada o Contrato (nunca proporciones fijas inventadas)
    if not detalle_grados:
        for sj in sede_jornadas:
            cup = int(sj.cupos or 0)
            if cup > 0:
                cupos_por_sede[sj.id_sede_id] += cup
                por_nivel['GENERAL_SEDE_JORNADA'] += cup
                detalle_grados.append({
                    'id_sede': sj.id_sede_id,
                    'nombre_sede': sj.id_sede.nombre_sede if sj.id_sede else '',
                    'id_jornada': sj.id_jornada_id,
                    'nombre_jornada': sj.id_jornada.nombre_jornada if sj.id_jornada else '',
                    'id_grado': None,
                    'nombre_grado': 'Cupos generales de jornada',
                    'nivel_educativo': 'GENERAL_SEDE_JORNADA',
                    'nombre_grupo_gramaje': '',
                    'cupos': cup,
                })

    if not detalle_grados:
        for c in contratos:
            cup = int(c.cupos or 0)
            if cup > 0 and c.id_sede_id:
                cupos_por_sede[c.id_sede_id] += cup
                por_nivel['GENERAL_CONTRATO'] += cup

    total_cupos = sum(cupos_por_sede.values()) or sum(int(c.cupos or 0) for c in contratos)
    return {
        'total_cupos': total_cupos,
        'por_nivel': dict(por_nivel),
        'cupos_por_sede': dict(cupos_por_sede),
        'cupos_por_grado_id': dict(cupos_por_grado_id),
        'detalle_grados': detalle_grados,
        'sede_jornada_ids': list(sj_map.keys()),
    }


def recopilar_datos_operativos_sirae(
    usuario,
    *,
    id_institucion=None,
    id_sede=None,
    id_jornada=None,
    id_contrato=None,
    fecha_desde: date | None = None,
    fecha_fin: date | None = None,
):
    """
    Motor unificado de consulta a la BD real de SIRAE respetando el alcance del usuario.
    Abastece tanto la generación de planillas (SIR-171) como los reportes consolidados (SIR-173)
    sin duplicar consultas ni utilizar datos ficticios.
    """
    alcance = _resolver_alcance_filtrado(
        usuario,
        id_institucion=id_institucion,
        id_sede=id_sede,
        id_jornada=id_jornada,
        id_contrato=id_contrato,
    )
    instituciones = alcance['instituciones']
    sedes = alcance['sedes']
    sedes_ids = alcance['sedes_ids']
    inst_ids = alcance['inst_ids']
    contratos = alcance['contratos']
    contrato_ids = alcance['contrato_ids']
    sede_jornadas = alcance['sede_jornadas']

    responsables = _resolver_responsables_reales(inst_ids, sedes_ids, contratos)
    cupos_info = _resolver_cupos_y_niveles(sede_jornadas, contratos)

    fecha_actualizacion = None
    ingredientes_all = Ingrediente.objects.select_related(
        'id_unidad_medida', 'id_categoria_inventario', 'id_tipo_mercado'
    )
    ingredientes_by_id = {ing.id_ingrediente: ing for ing in ingredientes_all}
    unidades_by_id = {u.id_unidad_medida: u for u in UnidadMedida.objects.all()}

    # 1. Gramajes activos reales
    gramajes_qs = Gramage.objects.filter(estado='ACTIVO').select_related(
        'id_ingrediente', 'id_grado', 'id_unidad_medida'
    )
    gramajes_rows = []
    gramaje_ids = []
    for g in gramajes_qs:
        gramaje_ids.append(g.id_gramaje)
        fecha_actualizacion = _actualizar_max_fecha(fecha_actualizacion, g.fecha_actualizacion)
        ing = g.id_ingrediente
        u = g.id_unidad_medida or (ing.id_unidad_medida if ing else None)
        gramajes_rows.append({
            'id_gramaje': g.id_gramaje,
            'id_ingrediente': g.id_ingrediente_id,
            'nombre_ingrediente': ing.nombre_ingrediente if ing else f'Producto {g.id_ingrediente_id}',
            'id_grado': g.id_grado_id,
            'nombre_grado': g.id_grado.nombre_grado if g.id_grado else 'General',
            'cantidad_gramaje': _to_float(g.cantidad_gramaje),
            'unidad_medida': (u.abreviatura or u.nombre) if u else '',
            'contexto_aplicacion': g.contexto_aplicacion,
        })

    # 2. Abastecimiento programado real por sede (reutilizando HU5) + CalculoEntrega históricos
    calculos_qs = CalculoEntrega.objects.filter(id_sede_id__in=sedes_ids) if sedes_ids else CalculoEntrega.objects.none()
    if id_contrato:
        calculos_qs = calculos_qs.filter(id_contrato_id=id_contrato)
    if id_jornada:
        calculos_qs = calculos_qs.filter(id_jornada_id=id_jornada)
    if fecha_desde:
        calculos_qs = calculos_qs.filter(fecha_referencia__gte=fecha_desde)
    if fecha_fin:
        calculos_qs = calculos_qs.filter(fecha_referencia__lte=fecha_fin)
    calculos_list = list(calculos_qs.order_by('-fecha_creacion'))
    calculo_ids = [c.id_calculo for c in calculos_list]
    for c in calculos_list:
        fecha_actualizacion = _actualizar_max_fecha(fecha_actualizacion, c.fecha_creacion)

    programado_por_ing = defaultdict(lambda: {'cantidad': 0.0, 'unidad': '', 'tipo_conservacion': '', 'sedes': set()})
    programacion_rows = []
    alertas_calculo = []
    dias_cobertura_max = 0

    for sede in sedes:
        calc_sede = calcular_abastecimiento_sede(
            sede,
            id_contrato=id_contrato,
            id_jornada=id_jornada,
            fecha_referencia=fecha_desde,
        )
        param = calc_sede.get('periodicidad') or {}
        dias_s = max(
            int(param.get('dias_perecederos') or 0),
            int(param.get('dias_no_perecederos') or 0),
            int(calc_sede.get('dias_calculados') or 0),
        )
        dias_cobertura_max = max(dias_cobertura_max, dias_s)
        for falta in calc_sede.get('faltantes_configuracion') or []:
            alertas_calculo.append({
                'sede': sede.nombre_sede,
                'tipo': falta.get('tipo'),
                'nivel': falta.get('nivel'),
                'mensaje': falta.get('mensaje'),
            })
        productos_calc = calc_sede.get('productos_sugeridos') or []
        for item in productos_calc:
            ing_id = item.get('id_ingrediente')
            cant = _to_float(item.get('cantidad_total_requerida') or item.get('consumo_teorico_periodo'))
            unidad = item.get('unidad_abreviatura') or item.get('unidad_medida') or ''
            tipo_cons = item.get('clasificacion_tipo') or ('Perecedero' if item.get('es_perecedero') else 'No perecedero')
            if ing_id is not None:
                entry = programado_por_ing[ing_id]
                entry['cantidad'] += cant
                entry['unidad'] = entry['unidad'] or unidad
                entry['tipo_conservacion'] = tipo_cons
                entry['sedes'].add(sede.id_sede)
            programacion_rows.append({
                'id_sede': sede.id_sede,
                'nombre_sede': sede.nombre_sede,
                'id_ingrediente': ing_id,
                'nombre_ingrediente': item.get('nombre_ingrediente') or '',
                'tipo_conservacion': tipo_cons,
                'gramaje_por_racion': _to_float(item.get('porcion_gramaje')),
                'cantidad_programada': round(cant, 3),
                'unidad': unidad,
                'dias_cobertura': item.get('dias_periodo'),
                'periodicidad': item.get('periodicidad_aplicada'),
            })

    # Complementar con CalculoEntrega histórico solo si para alguna sede no hubo cálculo dinámico activo
    sedes_con_prog_dinamica = {r['id_sede'] for r in programacion_rows}
    for c_hist in calculos_list:
        if c_hist.id_sede_id in sedes_con_prog_dinamica:
            continue
        for item in (c_hist.consolidado_snapshot or []):
            ing_id = item.get('id_ingrediente')
            cant = _to_float(item.get('cantidad_total_requerida') or item.get('consumo_teorico_periodo') or item.get('cantidad_requerida'))
            unidad = item.get('unidad_abreviatura') or item.get('unidad_medida') or ''
            tipo_cons = item.get('clasificacion_tipo') or ('Perecedero' if item.get('es_perecedero') else 'No perecedero')
            if ing_id is not None:
                entry = programado_por_ing[ing_id]
                entry['cantidad'] += cant
                entry['unidad'] = entry['unidad'] or unidad
                entry['tipo_conservacion'] = tipo_cons
                if c_hist.id_sede_id:
                    entry['sedes'].add(c_hist.id_sede_id)
            programacion_rows.append({
                'id_sede': c_hist.id_sede_id,
                'nombre_sede': c_hist.id_sede.nombre_sede if c_hist.id_sede_id and getattr(c_hist, 'id_sede', None) else '',
                'id_ingrediente': ing_id,
                'nombre_ingrediente': item.get('nombre_ingrediente') or '',
                'tipo_conservacion': tipo_cons,
                'gramaje_por_racion': _to_float(item.get('porcion_gramaje') or item.get('gramaje_por_racion')),
                'cantidad_programada': round(cant, 3),
                'unidad': unidad,
                'dias_cobertura': item.get('dias_periodo'),
                'periodicidad': item.get('periodicidad_aplicada'),
            })

    # 3. Entregas y recepciones reales
    entregas_qs = Entrega.objects.filter(id_sede_id__in=sedes_ids) if sedes_ids else Entrega.objects.none()
    if id_contrato:
        entregas_qs = entregas_qs.filter(id_contrato_id=id_contrato)
    if fecha_desde:
        entregas_qs = entregas_qs.filter(fecha_entrega__gte=fecha_desde)
    if fecha_fin:
        entregas_qs = entregas_qs.filter(fecha_entrega__lte=fecha_fin)
    entregas_list = list(entregas_qs.select_related('id_sede', 'id_contrato', 'id_usuario_receptor').order_by('-fecha_entrega', '-id_entrega'))
    entrega_ids = [e.id_entrega for e in entregas_list]
    sup_user_ids = {e.id_usuario_supervisor for e in entregas_list if e.id_usuario_supervisor}
    supervisores_by_id = Usuario.objects.in_bulk(sup_user_ids) if sup_user_ids else {}

    despachado_por_ing = defaultdict(float)
    recibido_por_ing = defaultdict(float)
    rechazado_por_ing = defaultdict(float)
    unidad_entrega_por_ing = {}
    entregas_rows = []
    recepciones_rows = []
    entregas_por_sede = defaultdict(list)

    for e in entregas_list:
        fecha_actualizacion = _actualizar_max_fecha(fecha_actualizacion, e.fecha_recepcion or e.fecha_entrega)
        ing = ingredientes_by_id.get(e.id_ingrediente)
        nombre_ing = ing.nombre_ingrediente if ing else f'Ingrediente #{e.id_ingrediente}'
        unidad_str = e.unidad or (ing.id_unidad_medida.abreviatura if ing and ing.id_unidad_medida else '')
        cant_desp = _to_float(e.cantidad)

        if e.estado in {'RECIBIDA', 'CON_NOVEDAD'}:
            cant_rec = _to_float(e.cantidad_recibida) if e.cantidad_recibida is not None else cant_desp
        elif e.estado == 'RECHAZADA':
            cant_rec = _to_float(e.cantidad_recibida) if e.cantidad_recibida is not None else 0.0
        else:
            cant_rec = 0.0

        if e.estado == 'RECHAZADA' and e.cantidad_rechazada is None:
            cant_rech = cant_desp
        else:
            cant_rech = _to_float(e.cantidad_rechazada)

        despachado_por_ing[e.id_ingrediente] += cant_desp
        recibido_por_ing[e.id_ingrediente] += cant_rec
        rechazado_por_ing[e.id_ingrediente] += cant_rech
        if unidad_str and e.id_ingrediente not in unidad_entrega_por_ing:
            unidad_entrega_por_ing[e.id_ingrediente] = unidad_str

        fila_entrega = {
            'id_entrega': e.id_entrega,
            'documento_entrega': e.documento_entrega or f'ENT-{e.id_entrega}',
            'id_sede': e.id_sede_id,
            'nombre_sede': e.id_sede.nombre_sede if e.id_sede else '',
            'id_contrato': e.id_contrato_id,
            'fecha_entrega': _iso(e.fecha_entrega),
            'fecha_recepcion': _iso(e.fecha_recepcion),
            'id_ingrediente': e.id_ingrediente,
            'nombre_ingrediente': nombre_ing,
            'unidad': unidad_str,
            'cantidad_requerida': _to_float(e.cantidad_requerida_calculo),
            'cantidad_despachada': cant_desp,
            'cantidad_recibida': cant_rec,
            'cantidad_rechazada': cant_rech,
            'diferencia_recepcion': round(cant_rec - cant_desp, 3),
            'frecuencia': e.frecuencia,
            'estado': e.estado,
            'motivo_rechazo': e.motivo_rechazo or '',
            'observaciones': e.observaciones or '',
            'supervisor': (
                supervisores_by_id[e.id_usuario_supervisor].nombre_completo
                if e.id_usuario_supervisor in supervisores_by_id
                else ''
            ),
            'receptor': e.id_usuario_receptor.nombre_completo if e.id_usuario_receptor else '',
        }
        entregas_rows.append(fila_entrega)
        recepciones_rows.append(fila_entrega)
        if e.id_sede_id:
            entregas_por_sede[e.id_sede_id].append(fila_entrega)

    # 4. Inventario y movimientos Kárdex (entradas/salidas reales)
    inv_qs = Inventario.objects.filter(id_sede_id__in=sedes_ids) if sedes_ids else Inventario.objects.none()
    inv_list = list(inv_qs.select_related('id_sede', 'id_institucion'))
    inventario_ids = [inv.id_inventario for inv in inv_list]

    entradas_rows = []
    salidas_rows = []
    entrada_ids = []
    salida_ids = []
    entradas_por_ing = defaultdict(float)
    salidas_por_ing = defaultdict(float)

    usuarios_scope_ids = set(responsables['usuarios_relacionados_ids'])
    if sedes_ids or inst_ids:
        filtro_mov = Q(id_usuario__id_sede_id__in=sedes_ids)
        if not id_sede and inst_ids:
            filtro_mov = filtro_mov | Q(id_usuario__id_sede__isnull=True, id_usuario__id_institucion_id__in=inst_ids)

        try:
            ent_qs = EntradaInventario.objects.filter(filtro_mov).select_related('id_ingrediente', 'id_usuario', 'id_unidad_medida')
            if fecha_desde:
                ent_qs = ent_qs.filter(fecha__date__gte=fecha_desde)
            if fecha_fin:
                ent_qs = ent_qs.filter(fecha__date__lte=fecha_fin)
            for ent in ent_qs.order_by('-fecha'):
                fecha_actualizacion = _actualizar_max_fecha(fecha_actualizacion, ent.fecha)
                entrada_ids.append(ent.id_entrada)
                cant = _to_float(ent.cantidad)
                entradas_por_ing[ent.id_ingrediente_id] += cant
                entradas_rows.append({
                    'id_movimiento': ent.id_entrada,
                    'tipo_movimiento': 'ENTRADA',
                    'fecha': _iso(ent.fecha),
                    'id_ingrediente': ent.id_ingrediente_id,
                    'nombre_ingrediente': ent.id_ingrediente.nombre_ingrediente if ent.id_ingrediente else '',
                    'cantidad': cant,
                    'unidad': ent.id_unidad_medida.abreviatura if ent.id_unidad_medida else '',
                    'usuario_responsable': ent.id_usuario.nombre_completo if ent.id_usuario else '',
                    'id_sede': ent.id_usuario.id_sede_id if ent.id_usuario else None,
                    'observaciones': ent.observaciones or '',
                })
        except DatabaseError:
            pass

        try:
            sal_qs = SalidaInventario.objects.filter(filtro_mov).select_related('id_ingrediente', 'id_usuario', 'id_unidad_medida')
            if fecha_desde:
                sal_qs = sal_qs.filter(fecha__date__gte=fecha_desde)
            if fecha_fin:
                sal_qs = sal_qs.filter(fecha__date__lte=fecha_fin)
            for sal in sal_qs.order_by('-fecha'):
                fecha_actualizacion = _actualizar_max_fecha(fecha_actualizacion, sal.fecha)
                salida_ids.append(sal.id_salida)
                cant = _to_float(sal.cantidad)
                salidas_por_ing[sal.id_ingrediente_id] += cant
                salidas_rows.append({
                    'id_movimiento': sal.id_salida,
                    'tipo_movimiento': 'SALIDA_COCINA',
                    'fecha': _iso(sal.fecha),
                    'id_ingrediente': sal.id_ingrediente_id,
                    'nombre_ingrediente': sal.id_ingrediente.nombre_ingrediente if sal.id_ingrediente else '',
                    'cantidad': cant,
                    'unidad': sal.id_unidad_medida.abreviatura if sal.id_unidad_medida else '',
                    'usuario_responsable': sal.id_usuario.nombre_completo if sal.id_usuario else '',
                    'id_sede': sal.id_usuario.id_sede_id if sal.id_usuario else None,
                    'observaciones': sal.observaciones or '',
                })
        except DatabaseError:
            pass

    inventario_rows = []
    bajo_stock_count = 0
    for inv in inv_list:
        ing = ingredientes_by_id.get(inv.id_ingrediente)
        u = unidades_by_id.get(inv.id_unidad_medida) or (ing.id_unidad_medida if ing else None)
        cat_nom = (
            ing.id_categoria_inventario.nombre_categoria
            if ing and ing.id_categoria_inventario and ing.id_categoria_inventario.nombre_categoria
            else 'Sin categoría'
        )
        actual = _to_float(inv.cantidad_actual)
        minimo = _to_float(inv.stock_minimo)
        if actual <= minimo:
            estado_stock = 'Stock Crítico / Bajo Mínimo'
            bajo_stock_count += 1
        elif actual <= (minimo * 1.35):
            estado_stock = 'Stock Preventivo'
        else:
            estado_stock = 'Disponible'
        inventario_rows.append({
            'id_inventario': inv.id_inventario,
            'id_sede': inv.id_sede_id,
            'nombre_sede': inv.id_sede.nombre_sede if inv.id_sede else '',
            'id_ingrediente': inv.id_ingrediente,
            'nombre_ingrediente': ing.nombre_ingrediente if ing else f'Ingrediente #{inv.id_ingrediente}',
            'categoria': cat_nom,
            'unidad': (u.abreviatura or u.nombre) if u else '',
            'total_entradas': round(entradas_por_ing.get(inv.id_ingrediente, 0.0), 3),
            'total_salidas': round(salidas_por_ing.get(inv.id_ingrediente, 0.0), 3),
            'cantidad_actual': actual,
            'stock_minimo': minimo,
            'estado_stock': estado_stock,
        })

    # 5. Menús y preparaciones reales
    menus_qs = Menu.objects.filter(id_contrato__in=contrato_ids).select_related('id_jornada') if contrato_ids else Menu.objects.none()
    if id_jornada:
        menus_qs = menus_qs.filter(id_jornada_id=id_jornada)
    if fecha_desde:
        menus_qs = menus_qs.filter(fecha__gte=fecha_desde)
    if fecha_fin:
        menus_qs = menus_qs.filter(fecha__lte=fecha_fin)
    menus_list = list(menus_qs.order_by('-fecha', '-id_menu'))
    menu_ids = [m.id_menu for m in menus_list]
    for m in menus_list:
        fecha_actualizacion = _actualizar_max_fecha(fecha_actualizacion, m.fecha)

    detalles_plato = list(
        DetallePlato.objects.filter(id_menu__in=menu_ids).select_related('id_plato')
    ) if menu_ids else []
    plato_ids = list({d.id_plato_id for d in detalles_plato if d.id_plato_id})

    prep_qs = PreparacionAsignada.objects.none()
    if menu_ids or usuarios_scope_ids:
        filtro_prep = Q()
        if menu_ids:
            filtro_prep |= Q(id_menu_id__in=menu_ids)
        if usuarios_scope_ids:
            filtro_prep |= Q(id_usuario_manipuladora_id__in=usuarios_scope_ids)
        prep_qs = PreparacionAsignada.objects.filter(filtro_prep).select_related(
            'id_menu', 'id_menu__id_jornada', 'id_plato', 'id_turno', 'id_usuario_manipuladora'
        )
        if fecha_desde:
            prep_qs = prep_qs.filter(fecha__gte=fecha_desde)
        if fecha_fin:
            prep_qs = prep_qs.filter(fecha__lte=fecha_fin)
    preparaciones_list = list(prep_qs.order_by('-fecha', '-id_preparacion_asignada'))
    preparacion_ids = [p.id_preparacion_asignada for p in preparaciones_list]

    preparaciones_rows = []
    for p in preparaciones_list:
        fecha_actualizacion = _actualizar_max_fecha(fecha_actualizacion, p.fecha)
        preparaciones_rows.append({
            'id_preparacion_asignada': p.id_preparacion_asignada,
            'fecha': _iso(p.fecha),
            'hora_programada': str(p.hora_programada or ''),
            'nombre_jornada': p.id_menu.id_jornada.nombre_jornada if (p.id_menu and p.id_menu.id_jornada) else '',
            'nombre_plato': p.id_plato.nombre_plato if p.id_plato else '',
            'ninos_presentes': int(p.id_menu.ninos_presentes or 0) if p.id_menu else 0,
            'nombre_turno': p.id_turno.nombre_turno if p.id_turno else '',
            'responsable_cocina': p.id_usuario_manipuladora.nombre_completo if p.id_usuario_manipuladora else '',
            'estado_preparacion': p.estado_preparacion or 'PENDIENTE',
            'observaciones': p.observaciones or '',
        })

    # Si hay menús sin PreparacionAsignada explícita, incorporar detalles de menús al listado de preparación/minuta
    if not preparaciones_rows and detalles_plato:
        menus_by_id = {m.id_menu: m for m in menus_list}
        for det in detalles_plato:
            m = menus_by_id.get(det.id_menu)
            preparaciones_rows.append({
                'id_preparacion_asignada': None,
                'fecha': _iso(m.fecha) if m else '',
                'hora_programada': '',
                'nombre_jornada': m.id_jornada.nombre_jornada if (m and m.id_jornada) else '',
                'nombre_plato': det.id_plato.nombre_plato if det.id_plato else '',
                'ninos_presentes': int(m.ninos_presentes or 0) if m else 0,
                'nombre_turno': '',
                'responsable_cocina': responsables['jefa_cocina_nombre'],
                'estado_preparacion': det.estado_preparacion or (m.estado if m else 'PROGRAMADO') or 'PROGRAMADO',
                'observaciones': '',
            })

    # Consumo inferido por receta solamente para productos donde no exista salida registrada en kárdex
    consumo_recetas_por_ing = defaultdict(float)
    if plato_ids and (preparaciones_list or menus_list):
        comps_por_plato = defaultdict(list)
        for comp in RecetaComponente.objects.filter(id_plato_id__in=plato_ids).select_related('id_ingrediente'):
            comps_por_plato[comp.id_plato_id].append(comp)
        menus_by_id = {m.id_menu: m for m in menus_list}
        # Priorizar preparaciones completadas; si no hay preparaciones, tomar detalles de menú ejecutados
        for p in preparaciones_list:
            st = (p.estado_preparacion or '').strip().lower()
            if st in {'anulado', 'cancelado', 'pendiente'}:
                continue
            raciones = int(p.id_menu.ninos_presentes or 0) if p.id_menu else 0
            for comp in comps_por_plato.get(p.id_plato_id, []):
                cant_base = _to_float(comp.cantidad)
                if comp.base_cantidad == 'POR_NINO':
                    consumo_recetas_por_ing[comp.id_ingrediente_id] += cant_base * max(raciones, 1)
                else:
                    consumo_recetas_por_ing[comp.id_ingrediente_id] += cant_base

    # 6. Asistencia diaria real (delimitada a usuarios y grados de las sedes autorizadas)
    asistencia_qs = AsistenciaDiaria.objects.none()
    if usuarios_scope_ids:
        asistencia_qs = AsistenciaDiaria.objects.filter(
            id_usuario_manipuladora__in=usuarios_scope_ids
        ).select_related('id_grado')
        if fecha_desde:
            asistencia_qs = asistencia_qs.filter(fecha__gte=fecha_desde)
        if fecha_fin:
            asistencia_qs = asistencia_qs.filter(fecha__lte=fecha_fin)
    asistencias_list = list(asistencia_qs.order_by('-fecha', 'id_grado__id_grado'))
    asistencia_ids = [a.id_asistencia for a in asistencias_list]

    asistencia_rows = []
    total_asistencia_reportada = 0
    for a in asistencias_list:
        fecha_actualizacion = _actualizar_max_fecha(fecha_actualizacion, a.fecha)
        cupos_g = cupos_info['cupos_por_grado_id'].get(a.id_grado_id, 0)
        presentes = int(a.ninos_presentes or 0)
        total_asistencia_reportada += presentes
        cobertura = round((presentes / cupos_g) * 100, 2) if cupos_g > 0 else 0.0
        asistencia_rows.append({
            'id_asistencia': a.id_asistencia,
            'fecha': _iso(a.fecha),
            'id_grado': a.id_grado_id,
            'nombre_grado': a.id_grado.nombre_grado if a.id_grado else f'Grado {a.id_grado_id}',
            'cupos_grado': cupos_g,
            'ninos_presentes': presentes,
            'diferencia_ausentismo': max(cupos_g - presentes, 0) if cupos_g > 0 else 0,
            'porcentaje_asistencia': cobertura,
        })

    # 7. Comparativo consolidado por producto (Programado vs Despachado vs Recibido vs Consumido)
    todos_ing_ids = (
        set(programado_por_ing.keys())
        | set(despachado_por_ing.keys())
        | set(recibido_por_ing.keys())
        | set(salidas_por_ing.keys())
        | set(consumo_recetas_por_ing.keys())
        | {inv.id_ingrediente for inv in inv_list}
    )

    comparativo_productos = []
    for ing_id in sorted(
        todos_ing_ids,
        key=lambda iid: (getattr(ingredientes_by_id.get(iid), 'nombre_ingrediente', '') or '').lower(),
    ):
        ing = ingredientes_by_id.get(ing_id)
        prog_info = programado_por_ing.get(ing_id)
        unidad = (
            (prog_info['unidad'] if prog_info else '')
            or unidad_entrega_por_ing.get(ing_id, '')
            or (ing.id_unidad_medida.abreviatura if ing and ing.id_unidad_medida else '')
        )
        prog_val = round(prog_info['cantidad'], 3) if prog_info else 0.0
        desp_val = round(despachado_por_ing.get(ing_id, 0.0), 3)
        rec_val = round(recibido_por_ing.get(ing_id, 0.0), 3)
        cons_kardex = salidas_por_ing.get(ing_id, 0.0)
        cons_val = round(cons_kardex if cons_kardex > 0 else consumo_recetas_por_ing.get(ing_id, 0.0), 3)

        estado_fila = 'COMPLETO'
        if prog_val > 0 and desp_val == 0:
            estado_fila = 'PENDIENTE_DESPACHO'
        elif desp_val > 0 and rec_val == 0:
            estado_fila = 'PENDIENTE_RECEPCION'
        elif rec_val > 0 and cons_val == 0:
            estado_fila = 'PENDIENTE_CONSUMO'

        comparativo_productos.append({
            'id_ingrediente': ing_id,
            'nombre_ingrediente': ing.nombre_ingrediente if ing else f'Ingrediente #{ing_id}',
            'tipo_conservacion': (
                prog_info['tipo_conservacion']
                if prog_info and prog_info['tipo_conservacion']
                else (ing.tipo_conservacion or 'Sin clasificar' if ing else 'Sin clasificar')
            ),
            'unidad': unidad,
            'cantidad_programada': prog_val,
            'cantidad_despachada': desp_val,
            'cantidad_recibida': rec_val,
            'cantidad_consumida': cons_val,
            'diferencia_despacho': round(desp_val - prog_val, 3),
            'diferencia_recepcion': round(rec_val - desp_val, 3),
            'saldo_remanente': round(rec_val - cons_val, 3),
            'estado_fila': estado_fila,
        })

    # 8. Consolidado por sede (SIR-173 y soporte tabla reportes)
    inv_por_sede = defaultdict(list)
    for r in inventario_rows:
        inv_por_sede[r['id_sede']].append(r)

    consolidado_sedes = []
    for sede in sedes:
        ents = entregas_por_sede.get(sede.id_sede, [])
        invs = inv_por_sede.get(sede.id_sede, [])
        prog_sede = sum(p['cantidad_programada'] for p in programacion_rows if p['id_sede'] == sede.id_sede)
        desp_sede = sum(e['cantidad_despachada'] for e in ents)
        rec_sede = sum(e['cantidad_recibida'] for e in ents)
        rech_sede = sum(e['cantidad_rechazada'] for e in ents)
        ultima = max((e['fecha_entrega'] for e in ents if e['fecha_entrega']), default='')
        consolidado_sedes.append({
            'id_sede': sede.id_sede,
            'nombre': sede.nombre_sede,
            'codigo_dane': sede.codigo_dane or '',
            'id_institucion': sede.id_institucion_id,
            'institucion_nombre': sede.id_institucion.nombre_institucion if sede.id_institucion else '',
            'cupos': cupos_info['cupos_por_sede'].get(sede.id_sede, 0),
            'entregas': len(ents),
            'recibidas': sum(1 for e in ents if e['estado'] in {'RECIBIDA', 'CON_NOVEDAD'}),
            'con_novedad': sum(1 for e in ents if e['estado'] in {'CON_NOVEDAD', 'RECHAZADA'}),
            'cantidad_programada': round(prog_sede, 3),
            'cantidad_despachada': round(desp_sede, 3),
            'cantidad_recibida': round(rec_sede, 3),
            'cantidad_rechazada': round(rech_sede, 3),
            'productos_bajo_minimo': sum(1 for r in invs if r['estado_stock'] == 'Stock Crítico / Bajo Mínimo'),
            'ultima_entrega': ultima,
        })

    return {
        'instituciones': instituciones,
        'sedes': sedes,
        'contratos': contratos,
        'responsables': responsables,
        'cupos': cupos_info,
        'dias_cobertura_max': dias_cobertura_max,
        'ingredientes_by_id': ingredientes_by_id,
        'gramajes_rows': gramajes_rows,
        'programacion_rows': programacion_rows,
        'entregas_rows': entregas_rows,
        'recepciones_rows': recepciones_rows,
        'inventario_rows': inventario_rows,
        'kardex_rows': sorted(entradas_rows + salidas_rows, key=lambda x: x['fecha'], reverse=True),
        'preparaciones_rows': preparaciones_rows,
        'asistencia_rows': asistencia_rows,
        'comparativo_productos': comparativo_productos,
        'consolidado_sedes': consolidado_sedes,
        'alertas_calculo': alertas_calculo,
        'bajo_stock_count': bajo_stock_count,
        'total_asistencia_reportada': total_asistencia_reportada,
        'fecha_actualizacion': (fecha_actualizacion or timezone.now()).isoformat(),
        'registros_origen': {
            'institucion_ids': inst_ids,
            'sede_ids': sedes_ids,
            'sede_jornada_ids': cupos_info['sede_jornada_ids'],
            'contrato_ids': contrato_ids,
            'gramaje_ids': gramaje_ids,
            'calculo_ids': calculo_ids,
            'entrega_ids': entrega_ids,
            'inventario_ids': inventario_ids,
            'entrada_ids': entrada_ids,
            'salida_ids': salida_ids,
            'menu_ids': menu_ids,
            'preparacion_ids': preparacion_ids,
            'asistencia_ids': asistencia_ids,
            'usuario_responsables_ids': [
                r['id_usuario']
                for r in (responsables['supervisores'] + responsables['administradores'] + responsables['jefas_cocina'])
            ],
        },
    }
