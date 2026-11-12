from collections import defaultdict
from decimal import Decimal
import uuid

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.facturas_compra.models import InventarioCentral
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.instituciones.models import Institucion
from apps_sirae.inventario.models import AsignacionInventario, Inventario
from apps_sirae.sedes.models import Sede
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.unidades_medida.services import ErrorConversionUnidad, convertir_cantidad


TOLERANCIA = Decimal('0.001')


def _normalizar_unidad(valor: str | None) -> str:
    return str(valor or '').strip().lower()


def _resolver_unidad_por_nombre(texto: str | None, unidades_map: dict[str, UnidadMedida]) -> UnidadMedida | None:
    if not texto:
        return None
    return unidades_map.get(_normalizar_unidad(texto))


def _convertir_seguro(
    cantidad: Decimal,
    unidad_origen: UnidadMedida | None,
    unidad_destino: UnidadMedida | None,
    ingrediente: Ingrediente | None = None,
) -> Decimal:
    if not unidad_origen or not unidad_destino or unidad_origen.pk == unidad_destino.pk:
        return cantidad
    return convertir_cantidad(cantidad, unidad_origen, unidad_destino, ingrediente=ingrediente)


def obtener_pendiente_asignado_central(ingrediente_ids=None) -> dict[int, Decimal]:
    """
    Retorna por id_ingrediente la suma pendiente por despachar (en la unidad base de InventarioCentral/Ingrediente)
    para todas las asignaciones ACTIVAS en todas las instituciones.
    """
    qs = AsignacionInventario.objects.filter(estado='ACTIVA').select_related(
        'id_ingrediente',
        'id_ingrediente__id_unidad_medida',
        'id_unidad_medida',
    )
    if ingrediente_ids is not None:
        qs = qs.filter(id_ingrediente_id__in=list(ingrediente_ids))

    central_units = {
        ic.id_ingrediente_id: ic.id_unidad_medida
        for ic in InventarioCentral.objects.select_related('id_unidad_medida').all()
    }

    pendientes: dict[int, Decimal] = defaultdict(lambda: Decimal('0.000'))
    for asig in qs:
        pend = asig.cantidad_pendiente
        if pend <= 0:
            continue
        ing = asig.id_ingrediente
        u_dest = central_units.get(asig.id_ingrediente_id) or (ing.id_unidad_medida if ing else None)
        u_orig = asig.id_unidad_medida or (ing.id_unidad_medida if ing else None)
        try:
            pend_conv = _convertir_seguro(pend, u_orig, u_dest, ing)
        except ErrorConversionUnidad:
            pend_conv = pend
        pendientes[asig.id_ingrediente_id] += pend_conv
    return pendientes


def calcular_saldos_centrales(ingrediente_ids=None) -> dict[int, dict]:
    """Calcula stock físico, reservado en asignaciones activas y saldo libre para asignar."""
    qs = InventarioCentral.objects.select_related('id_ingrediente', 'id_unidad_medida')
    if ingrediente_ids is not None:
        qs = qs.filter(id_ingrediente_id__in=list(ingrediente_ids))

    centrales = list(qs)
    pendientes_map = obtener_pendiente_asignado_central(ingrediente_ids)
    resultado: dict[int, dict] = {}
    for ic in centrales:
        fisico = Decimal(str(ic.cantidad_disponible or '0.000'))
        reservado = pendientes_map.get(ic.id_ingrediente_id, Decimal('0.000'))
        libre = max(Decimal('0.000'), fisico - reservado)
        resultado[ic.id_ingrediente_id] = {
            'inventario_central': ic,
            'unidad': ic.id_unidad_medida or ic.id_ingrediente.id_unidad_medida,
            'stock_fisico': fisico,
            'asignado_pendiente': reservado,
            'saldo_libre': libre,
        }
    return resultado


def obtener_resumen_asignaciones_institucion(institucion_id: int, *, solo_activas: bool = False) -> dict:
    """Consolida por ingrediente lo asignado, despachado y pendiente de una institución."""
    estados = ['ACTIVA'] if solo_activas else ['ACTIVA', 'COMPLETADA']
    qs = AsignacionInventario.objects.filter(
        id_institucion_id=institucion_id,
        estado__in=estados,
    ).select_related(
        'id_ingrediente',
        'id_ingrediente__id_unidad_medida',
        'id_ingrediente__id_tipo_mercado',
        'id_unidad_medida',
    ).order_by('id_asignacion')

    saldos_central = calcular_saldos_centrales()
    por_ing: dict[int, dict] = {}

    for asig in qs:
        ing_id = asig.id_ingrediente_id
        ing = asig.id_ingrediente
        saldo_c = saldos_central.get(ing_id)
        u_dest = (saldo_c['unidad'] if saldo_c else None) or (ing.id_unidad_medida if ing else None) or asig.id_unidad_medida
        u_orig = asig.id_unidad_medida or u_dest

        try:
            asig_conv = _convertir_seguro(Decimal(str(asig.cantidad_asignada or '0')), u_orig, u_dest, ing)
            desp_conv = _convertir_seguro(Decimal(str(asig.cantidad_despachada or '0')), u_orig, u_dest, ing)
        except ErrorConversionUnidad:
            asig_conv = Decimal(str(asig.cantidad_asignada or '0'))
            desp_conv = Decimal(str(asig.cantidad_despachada or '0'))

        pend_conv = max(Decimal('0.000'), asig_conv - desp_conv)

        if ing_id not in por_ing:
            por_ing[ing_id] = {
                'id_ingrediente': ing_id,
                'nombre_ingrediente': ing.nombre_ingrediente if ing else f'Ingrediente #{ing_id}',
                'id_tipo_mercado': ing.id_tipo_mercado_id if ing else None,
                'id_unidad_medida': u_dest.id_unidad_medida if u_dest else None,
                'unidad': (u_dest.abreviatura or u_dest.nombre) if u_dest else 'Und',
                'cantidad_asignada': Decimal('0.000'),
                'cantidad_despachada': Decimal('0.000'),
                'cantidad_pendiente': Decimal('0.000'),
                'stock_bodega_central': saldo_c['stock_fisico'] if saldo_c else Decimal('0.000'),
                'saldo_libre_asignar': saldo_c['saldo_libre'] if saldo_c else Decimal('0.000'),
                'asignaciones_ids': [],
            }

        entry = por_ing[ing_id]
        entry['cantidad_asignada'] += asig_conv
        entry['cantidad_despachada'] += desp_conv
        entry['cantidad_pendiente'] += pend_conv
        entry['asignaciones_ids'].append(asig.id_asignacion)

    items = []
    for entry in sorted(por_ing.values(), key=lambda x: x['nombre_ingrediente'].lower()):
        items.append({
            **entry,
            'cantidad_asignada': float(round(entry['cantidad_asignada'], 3)),
            'cantidad_despachada': float(round(entry['cantidad_despachada'], 3)),
            'cantidad_pendiente': float(round(entry['cantidad_pendiente'], 3)),
            'stock_bodega_central': float(round(entry['stock_bodega_central'], 3)),
            'saldo_libre_asignar': float(round(entry['saldo_libre_asignar'], 3)),
        })

    tiene_cualquier_asignacion = AsignacionInventario.objects.filter(
        id_institucion_id=institucion_id,
        estado__in=['ACTIVA', 'COMPLETADA'],
    ).exists()

    return {
        'id_institucion': int(institucion_id),
        'tiene_asignaciones': tiene_cualquier_asignacion,
        'tiene_saldo_pendiente': any(i['cantidad_pendiente'] > 0 for i in items),
        'items': items,
        'mapa_por_ingrediente': {i['id_ingrediente']: i for i in items},
    }


def sugerir_asignacion_institucion(
    institucion_id: int,
    *,
    id_contrato: int | None = None,
    dias_perecederos: int | None = None,
    dias_no_perecederos: int | None = None,
    incluir_todos_gramajes: bool = False,
) -> dict:
    """
    Consolida los requerimientos calculados de todas las sedes activas de la institución
    (usando los cupos repartidos por el Administrador) y los compara contra el saldo libre de Bodega Central.
    """
    from apps_sirae.entregas.services import calcular_abastecimiento_sede

    inst = Institucion.objects.filter(pk=institucion_id).first()
    if not inst:
        raise LookupError(f"La institución con id {institucion_id} no existe.")

    sedes = list(Sede.objects.filter(id_institucion=inst, estado='ACTIVO').select_related('id_institucion').order_by('id_sede'))
    contrato = None
    if id_contrato:
        contrato = Contrato.objects.filter(pk=id_contrato, id_institucion=inst).first()
    if not contrato:
        contrato = Contrato.objects.filter(id_institucion=inst).order_by('-id_contrato').first()

    saldos_central = calcular_saldos_centrales()
    resumen_actual = obtener_resumen_asignaciones_institucion(inst.id_institucion, solo_activas=True)
    pendiente_inst_map = {
        i['id_ingrediente']: Decimal(str(i['cantidad_pendiente']))
        for i in resumen_actual['items']
    }

    unidades_by_key = {}
    for u in UnidadMedida.objects.all():
        if u.abreviatura:
            unidades_by_key[_normalizar_unidad(u.abreviatura)] = u
        if u.nombre:
            unidades_by_key[_normalizar_unidad(u.nombre)] = u

    agregados: dict[int, dict] = {}
    faltantes = []
    vistas_faltantes = set()
    total_cupos_sedes = 0

    for sede in sedes:
        calc = calcular_abastecimiento_sede(
            sede,
            dias_perecederos_override=dias_perecederos,
            dias_no_perecederos_override=dias_no_perecederos,
            id_contrato=contrato.id_contrato if contrato else None,
            incluir_todos_gramajes=incluir_todos_gramajes,
        )
        total_cupos_sedes += int(calc.get('total_cupos') or 0)
        for f in calc.get('faltantes_configuracion') or []:
            clave = (sede.nombre_sede, f.get('tipo'), f.get('mensaje'))
            if clave not in vistas_faltantes:
                vistas_faltantes.add(clave)
                faltantes.append({'sede': sede.nombre_sede, **f})

        for sug in calc.get('productos_sugeridos') or []:
            ing_id = sug.get('id_ingrediente')
            if not ing_id:
                continue
            saldo_c = saldos_central.get(ing_id)
            ing_obj = saldo_c['inventario_central'].id_ingrediente if saldo_c else Ingrediente.objects.filter(pk=ing_id).first()
            u_dest = (saldo_c['unidad'] if saldo_c else None) or (ing_obj.id_unidad_medida if ing_obj else None)
            u_orig = _resolver_unidad_por_nombre(sug.get('unidad_abreviatura') or sug.get('unidad_medida'), unidades_by_key) or u_dest

            req_sede = Decimal(str(sug.get('cantidad_sugerida_despacho') or 0))
            req_bruto = Decimal(str(sug.get('cantidad_total_requerida') or 0))
            try:
                req_sede = _convertir_seguro(req_sede, u_orig, u_dest, ing_obj)
                req_bruto = _convertir_seguro(req_bruto, u_orig, u_dest, ing_obj)
            except ErrorConversionUnidad:
                pass

            if ing_id not in agregados:
                agregados[ing_id] = {
                    'id_ingrediente': ing_id,
                    'nombre_ingrediente': sug.get('nombre_ingrediente') or (ing_obj.nombre_ingrediente if ing_obj else f'Ingrediente #{ing_id}'),
                    'es_perecedero': bool(sug.get('es_perecedero')),
                    'id_unidad_medida': u_dest.id_unidad_medida if u_dest else None,
                    'unidad': (u_dest.abreviatura or u_dest.nombre) if u_dest else (sug.get('unidad_abreviatura') or 'Und'),
                    'requerido_total_sedes': Decimal('0.000'),
                    'necesidad_neta_sedes': Decimal('0.000'),
                    'sedes_detalle': [],
                }

            agregados[ing_id]['requerido_total_sedes'] += req_bruto
            agregados[ing_id]['necesidad_neta_sedes'] += req_sede
            agregados[ing_id]['sedes_detalle'].append({
                'id_sede': sede.id_sede,
                'nombre_sede': sede.nombre_sede,
                'necesidad_neta': float(round(req_sede, 3)),
            })

    if not sedes:
        faltantes.append({
            'sede': None,
            'tipo': 'SEDES',
            'nivel': 'ADVERTENCIA',
            'mensaje': 'La institución no tiene sedes activas configuradas; puedes asignar cantidades manualmente.',
        })

    sugerencias = []
    for ing_id, item in sorted(agregados.items(), key=lambda kv: kv[1]['nombre_ingrediente'].lower()):
        saldo_c = saldos_central.get(ing_id)
        fisico = saldo_c['stock_fisico'] if saldo_c else Decimal('0.000')
        libre = saldo_c['saldo_libre'] if saldo_c else Decimal('0.000')
        ya_asignado_pend = pendiente_inst_map.get(ing_id, Decimal('0.000'))
        faltante_por_asignar = max(Decimal('0.000'), item['necesidad_neta_sedes'] - ya_asignado_pend)
        sugerido_asignar = min(faltante_por_asignar, libre) if libre > 0 else Decimal('0.000')

        sugerencias.append({
            'id_ingrediente': ing_id,
            'nombre_ingrediente': item['nombre_ingrediente'],
            'es_perecedero': item['es_perecedero'],
            'id_unidad_medida': item['id_unidad_medida'],
            'unidad': item['unidad'],
            'requerido_total_sedes': float(round(item['requerido_total_sedes'], 3)),
            'necesidad_neta_sedes': float(round(item['necesidad_neta_sedes'], 3)),
            'ya_asignado_pendiente': float(round(ya_asignado_pend, 3)),
            'faltante_por_asignar': float(round(faltante_por_asignar, 3)),
            'sugerido_asignar': float(round(sugerido_asignar, 3)),
            'stock_bodega_central': float(round(fisico, 3)),
            'saldo_libre_asignar': float(round(libre, 3)),
            'alcance_bodega': 'SUFICIENTE' if libre >= faltante_por_asignar else 'INSUFICIENTE',
            'sedes_detalle': item['sedes_detalle'],
        })

    return {
        'id_institucion': inst.id_institucion,
        'nombre_institucion': inst.nombre_institucion,
        'id_contrato': contrato.id_contrato if contrato else None,
        'numero_cor': contrato.numero_cor if contrato else None,
        'cupos_contrato': contrato.cupos if contrato else 0,
        'total_sedes_activas': len(sedes),
        'total_cupos_sedes': total_cupos_sedes,
        'faltantes_configuracion': faltantes,
        'productos_sugeridos': sugerencias,
    }


def asignar_inventario_lote(usuario, data: dict) -> dict:
    """
    Reserva cantidades desde Bodega Central (InventarioCentral) hacia una institución educativa.
    No descuenta `cantidad_disponible` físico aún; ese descuento ocurre al salir la entrega física.
    """
    id_inst = data.get('id_institucion')
    items = data.get('items') or []
    if not id_inst:
        raise ValidationError({'error': "El campo 'id_institucion' es obligatorio."})
    if not isinstance(items, list) or not items:
        raise ValidationError({'error': "Debe incluir al menos un ingrediente en 'items'."})

    inst = Institucion.objects.filter(pk=id_inst).first()
    if not inst:
        raise LookupError(f"La institución con id {id_inst} no existe.")

    contrato = None
    if data.get('id_contrato'):
        contrato = Contrato.objects.filter(pk=data.get('id_contrato'), id_institucion=inst).first()
    if not contrato:
        contrato = Contrato.objects.filter(id_institucion=inst).order_by('-id_contrato').first()

    periodo_inicio = data.get('periodo_inicio') or None
    periodo_fin = data.get('periodo_fin') or None
    observaciones = str(data.get('observaciones') or '').strip()
    codigo_lote = f"ASIG-{inst.id_institucion}-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:5].upper()}"
    user_asignador = usuario if getattr(usuario, 'is_authenticated', False) and hasattr(usuario, '_meta') else None

    creadas = []
    with transaction.atomic():
        # Consolidar cantidades repetidas del mismo ingrediente en el payload
        acum_por_ing: dict[int, dict] = {}
        for item in items:
            raw_ing = item.get('id_ingrediente')
            raw_cant = item.get('cantidad') or item.get('cantidad_asignada')
            if not raw_ing or raw_cant is None:
                continue
            try:
                ing_id = int(raw_ing)
                cant_dec = Decimal(str(raw_cant))
            except Exception:
                raise ValidationError({'error': f"Cantidad inválida para ingrediente {raw_ing}."})

            if not cant_dec.is_finite() or cant_dec <= 0:
                raise ValidationError({'error': f"La cantidad del ingrediente {ing_id} debe ser mayor a cero."})

            ing = Ingrediente.objects.select_related('id_unidad_medida').filter(pk=ing_id).first()
            if not ing:
                raise ValidationError({'error': f"El ingrediente {ing_id} no existe."})

            inv_c = InventarioCentral.objects.select_for_update().filter(id_ingrediente=ing).first()
            if not inv_c:
                raise ValidationError({
                    'error': f"No hay existencias en Stock Global para '{ing.nombre_ingrediente}'."
                })

            u_dest = inv_c.id_unidad_medida or ing.id_unidad_medida
            u_item_id = item.get('id_unidad_medida')
            u_item = UnidadMedida.objects.filter(pk=u_item_id).first() if u_item_id else u_dest

            try:
                cant_en_central = _convertir_seguro(cant_dec, u_item, u_dest, ing)
            except ErrorConversionUnidad as exc:
                raise ValidationError({'error': str(exc)})

            if ing_id not in acum_por_ing:
                acum_por_ing[ing_id] = {
                    'ing': ing,
                    'inv_c': inv_c,
                    'unidad': u_dest,
                    'cantidad': Decimal('0.000'),
                }
            acum_por_ing[ing_id]['cantidad'] += cant_en_central

        if not acum_por_ing:
            raise ValidationError({'error': "Debe incluir al menos un ingrediente válido con cantidad mayor a cero."})

        pendientes_central = obtener_pendiente_asignado_central(acum_por_ing.keys())
        for ing_id, entry in acum_por_ing.items():
            fisico = Decimal(str(entry['inv_c'].cantidad_disponible or '0.000'))
            reservado = pendientes_central.get(ing_id, Decimal('0.000'))
            libre = max(Decimal('0.000'), fisico - reservado)
            if entry['cantidad'] > libre + TOLERANCIA:
                u_txt = (entry['unidad'].abreviatura or entry['unidad'].nombre) if entry['unidad'] else ''
                raise ValidationError({
                    'error': (
                        f"Stock libre insuficiente en Bodega Central para '{entry['ing'].nombre_ingrediente}'. "
                        f"Disponible para asignar: {float(round(libre, 3))} {u_txt}, "
                        f"solicitado: {float(round(entry['cantidad'], 3))} {u_txt}."
                    )
                })

            asig = AsignacionInventario.objects.create(
                codigo_lote=codigo_lote,
                id_institucion=inst,
                id_contrato=contrato,
                id_ingrediente=entry['ing'],
                id_unidad_medida=entry['unidad'],
                cantidad_asignada=entry['cantidad'].quantize(Decimal('0.001')),
                cantidad_despachada=Decimal('0.000'),
                periodo_inicio=periodo_inicio,
                periodo_fin=periodo_fin,
                estado='ACTIVA',
                observaciones=observaciones,
                id_usuario_asignador=user_asignador,
            )
            creadas.append(asig)

    return {
        'codigo_lote': codigo_lote,
        'institucion': inst,
        'asignaciones': creadas,
    }


def anular_asignacion_inventario(asignacion: AsignacionInventario, motivo: str = '') -> AsignacionInventario:
    """Libera el saldo pendiente de una asignación sin alterar lo ya despachado."""
    with transaction.atomic():
        asig = AsignacionInventario.objects.select_for_update().get(pk=asignacion.pk)
        if asig.estado == 'ANULADA':
            raise ValidationError({'error': 'Esta asignación ya se encuentra anulada.'})

        despachada = Decimal(str(asig.cantidad_despachada or '0.000'))
        if despachada > 0:
            asig.cantidad_asignada = despachada
            asig.estado = 'COMPLETADA'
        else:
            asig.estado = 'ANULADA'

        if motivo:
            asig.observaciones = f"{asig.observaciones} | Anulación: {motivo}".strip(' |')
        asig.save()
        return asig


def consumir_asignacion_institucion_fifo(
    institucion_id: int,
    id_ingrediente: int,
    cantidad_despacho: Decimal,
    unidad_despacho_nombre: str = '',
    *,
    validar_saldo: bool = False,
) -> bool:
    """
    Descuenta FIFO del saldo pendiente en AsignacionInventario(ACTIVA) para la institución.
    Si `validar_saldo` es True y el saldo pendiente es menor a lo solicitado, lanza ValidationError.
    Retorna True si descontó al menos una asignación.
    """
    if not institucion_id or not id_ingrediente or cantidad_despacho <= 0:
        return False

    asignaciones = list(
        AsignacionInventario.objects.select_for_update()
        .filter(
            id_institucion_id=institucion_id,
            id_ingrediente_id=id_ingrediente,
            estado='ACTIVA',
        )
        .select_related('id_ingrediente', 'id_ingrediente__id_unidad_medida', 'id_unidad_medida')
        .order_by('fecha_asignacion', 'id_asignacion')
    )

    if not asignaciones:
        if validar_saldo:
            ing_nom = Ingrediente.objects.filter(pk=id_ingrediente).values_list('nombre_ingrediente', flat=True).first() or f"Ingrediente #{id_ingrediente}"
            raise ValidationError({
                'error': (
                    f"La institución no tiene inventario asignado por SuperAdmin para '{ing_nom}'. "
                    "Solicita la asignación desde Stock Global antes de despachar."
                ),
                'requiere_asignacion_inventario': True,
            })
        return False

    unidades_by_key = {}
    for u in UnidadMedida.objects.all():
        if u.abreviatura:
            unidades_by_key[_normalizar_unidad(u.abreviatura)] = u
        if u.nombre:
            unidades_by_key[_normalizar_unidad(u.nombre)] = u
    u_desp = _resolver_unidad_por_nombre(unidad_despacho_nombre, unidades_by_key)

    # Validar disponibilidad total en unidad de la primera asignación (o central)
    total_pend_ref = Decimal('0.000')
    ref_asig = asignaciones[0]
    u_ref = ref_asig.id_unidad_medida or (ref_asig.id_ingrediente.id_unidad_medida if ref_asig.id_ingrediente else None)
    ing_obj = ref_asig.id_ingrediente

    try:
        cant_en_ref = _convertir_seguro(cantidad_despacho, u_desp or u_ref, u_ref, ing_obj)
    except ErrorConversionUnidad:
        cant_en_ref = cantidad_despacho

    for a in asignaciones:
        pend = a.cantidad_pendiente
        u_a = a.id_unidad_medida or u_ref
        try:
            total_pend_ref += _convertir_seguro(pend, u_a, u_ref, ing_obj)
        except ErrorConversionUnidad:
            total_pend_ref += pend

    if validar_saldo and cant_en_ref > total_pend_ref + TOLERANCIA:
        u_txt = (u_ref.abreviatura or u_ref.nombre) if u_ref else ''
        nom_ing = ing_obj.nombre_ingrediente if ing_obj else f"Ingrediente #{id_ingrediente}"
        raise ValidationError({
            'error': (
                f"El despacho de '{nom_ing}' ({float(round(cant_en_ref, 3))} {u_txt}) supera el saldo asignado "
                f"a la institución ({float(round(total_pend_ref, 3))} {u_txt})."
            ),
            'requiere_asignacion_inventario': True,
        })

    restante = cant_en_ref
    for a in asignaciones:
        if restante <= Decimal('0.000'):
            break
        u_a = a.id_unidad_medida or u_ref
        pend_a = a.cantidad_pendiente
        if pend_a <= 0:
            a.estado = 'COMPLETADA'
            a.save(update_fields=['estado', 'fecha_actualizacion'])
            continue

        try:
            restante_en_a = _convertir_seguro(restante, u_ref, u_a, ing_obj)
        except ErrorConversionUnidad:
            restante_en_a = restante

        consumir_a = min(pend_a, restante_en_a)
        a.cantidad_despachada = (Decimal(str(a.cantidad_despachada or '0')) + consumir_a).quantize(Decimal('0.001'))
        if a.cantidad_pendiente <= TOLERANCIA:
            a.estado = 'COMPLETADA'
        a.save(update_fields=['cantidad_despachada', 'estado', 'fecha_actualizacion'])

        try:
            consumido_en_ref = _convertir_seguro(consumir_a, u_a, u_ref, ing_obj)
        except ErrorConversionUnidad:
            consumido_en_ref = consumir_a
        restante = max(Decimal('0.000'), restante - consumido_en_ref)

    return True


def inicializar_canasta_sede(id_sede: int, solo_faltantes: bool = True) -> int:
    """
    Puebla el inventario de una sede con la lista de ingredientes oficiales del PAE (stock 0.00)
    para que la sede nunca empiece vacía y la cocina tenga el catálogo listo.
    """
    from apps_sirae.sedes.models import Sede
    from apps_sirae.ingredientes.models import Ingrediente

    sede = Sede.objects.filter(pk=id_sede).select_related('id_institucion').first()
    if not sede:
        return 0

    ingredientes = list(Ingrediente.objects.all().order_by('id_ingrediente'))
    existentes_ids = set(
        Inventario.objects.filter(id_sede=sede).values_list('id_ingrediente', flat=True)
    )

    creados = 0
    with transaction.atomic():
        for ing in ingredientes:
            if ing.id_ingrediente in existentes_ids and solo_faltantes:
                continue
            u_id = ing.id_unidad_medida_id or 1
            Inventario.objects.create(
                id_ingrediente=ing.id_ingrediente,
                cantidad_actual=Decimal('0.00'),
                stock_minimo=Decimal('0.00'),
                id_unidad_medida=u_id,
                id_institucion=sede.id_institucion,
                id_sede=sede,
            )
            creados += 1

    return creados


