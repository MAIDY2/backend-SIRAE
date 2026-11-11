import csv
import io

from rest_framework.exceptions import PermissionDenied

from apps_sirae.reportes.models import PlanillaGenerada
from apps_sirae.reportes.services.catalogo_fuentes import usuario_rol_canonico
from apps_sirae.reportes.services.generador_planillas import _parse_fecha
from apps_sirae.reportes.services.recopilador_sirae import recopilar_datos_operativos_sirae
from apps_sirae.usuarios.alcance import describir_alcance_usuario


TIPOS_REPORTE_CONSOLIDADO = [
    {
        'codigo': 'RESUMEN_GENERAL',
        'nombre': 'Resumen general de la operación',
        'descripcion': 'Vista general con totales de entregas, inventarios, asistencia y consumo.',
        'roles_autorizados': ['SuperAdministrador', 'supervisor', 'Administrador'],
    },
    {
        'codigo': 'CONTRATOS_CUPOS',
        'nombre': 'Contratos y cupos asignados',
        'descripcion': 'Contratos activos, operador asignado y cupos por sede y jornada.',
        'roles_autorizados': ['SuperAdministrador', 'supervisor'],
    },
    {
        'codigo': 'GRAMAJES_PROYECTADOS',
        'nombre': 'Gramajes y alimentos proyectados',
        'descripcion': 'Cantidades proyectadas de alimentos según cupos, gramajes y cobertura.',
        'roles_autorizados': ['SuperAdministrador', 'supervisor'],
    },
    {
        'codigo': 'PROGRAMACION_ENTREGAS',
        'nombre': 'Programación y entregas despachadas',
        'descripcion': 'Control de mercados programados y entregas despachadas hacia cada sede.',
        'roles_autorizados': ['SuperAdministrador', 'supervisor'],
    },
    {
        'codigo': 'RECEPCIONES_DIFERENCIAS',
        'nombre': 'Recepciones y diferencias de entrega',
        'descripcion': 'Comparativo entre lo despachado, lo recibido en sede y los rechazos o diferencias.',
        'roles_autorizados': ['SuperAdministrador', 'supervisor', 'Administrador'],
    },
    {
        'codigo': 'INVENTARIO_CONSOLIDADO',
        'nombre': 'Inventario actual y stock mínimo',
        'descripcion': 'Existencias actuales por producto en bodega y alertas de stock bajo.',
        'roles_autorizados': ['SuperAdministrador', 'Administrador'],
    },
    {
        'codigo': 'MOVIMIENTOS_KARDEX',
        'nombre': 'Entradas y salidas de inventario (Kárdex)',
        'descripcion': 'Historial de entradas por recepción y salidas registradas hacia cocina.',
        'roles_autorizados': ['SuperAdministrador', 'Administrador'],
    },
    {
        'codigo': 'MENUS_PREPARACIONES',
        'nombre': 'Menús y preparaciones del comedor',
        'descripcion': 'Platos, porciones y preparaciones ejecutadas por jornada en la institución.',
        'roles_autorizados': ['SuperAdministrador', 'Administrador'],
    },
    {
        'codigo': 'ASISTENCIA_GRADOS',
        'nombre': 'Asistencia diaria por grado',
        'descripcion': 'Cobertura de estudiantes atendidos por grado escolar frente a cupos.',
        'roles_autorizados': ['SuperAdministrador', 'Administrador'],
    },
    {
        'codigo': 'CONSUMO_ALIMENTOS',
        'nombre': 'Consumo real vs programado y recibido',
        'descripcion': 'Comparativo entre lo programado, despachado, recibido y consumido por producto.',
        'roles_autorizados': ['SuperAdministrador', 'supervisor', 'Administrador'],
    },
    {
        'codigo': 'NOVEDADES_INCONSISTENCIAS',
        'nombre': 'Novedades e inconsistencias',
        'descripcion': 'Alertas de entregas rechazadas, diferencias, stock bajo o planillas pendientes.',
        'roles_autorizados': ['SuperAdministrador', 'supervisor', 'Administrador'],
    },
]


def obtener_tipos_reporte_para_usuario(usuario) -> list[dict]:
    """Devuelve únicamente los tipos de reporte consolidado habilitados para el rol del usuario."""
    rol = usuario_rol_canonico(usuario)
    if rol == 'SuperAdministrador':
        return [dict(item) for item in TIPOS_REPORTE_CONSOLIDADO]
    return [
        dict(item)
        for item in TIPOS_REPORTE_CONSOLIDADO
        if rol in (item.get('roles_autorizados') or [])
    ]


def _construir_filas_contratos_cupos(datos: dict) -> list[dict]:
    contratos_by_sede = {}
    for c in datos['contratos']:
        contratos_by_sede.setdefault(c.id_sede_id, []).append(c)

    filas = []
    for item in datos['cupos']['detalle_grados']:
        cont_list = contratos_by_sede.get(item['id_sede']) or datos['contratos']
        c = cont_list[0] if cont_list else None
        filas.append({
            'nombre_sede': item['nombre_sede'],
            'nombre_jornada': item['nombre_jornada'],
            'nombre_grado': item['nombre_grado'],
            'nivel_educativo': item['nivel_educativo'],
            'nombre_grupo_gramaje': item['nombre_grupo_gramaje'],
            'cupos': item['cupos'],
            'contrato': c.numero_cor if c else 'Sin contrato',
            'operador': c.institucion if c else '',
            'estado_contrato': c.estado if c else '',
        })
    if not filas:
        for c in datos['contratos']:
            filas.append({
                'nombre_sede': c.id_sede.nombre_sede if c.id_sede else 'Institucional',
                'nombre_jornada': c.id_jornada.nombre_jornada if c.id_jornada else 'General',
                'nombre_grado': 'Cupos de contrato',
                'nivel_educativo': 'GENERAL',
                'nombre_grupo_gramaje': '',
                'cupos': int(c.cupos or 0),
                'contrato': c.numero_cor,
                'operador': c.institucion,
                'estado_contrato': c.estado,
            })
    return filas


def _construir_filas_novedades(datos: dict, planillas_qs) -> list[dict]:
    novedades = []
    for e in datos['recepciones_rows']:
        dif = round(e['cantidad_recibida'] - e['cantidad_despachada'], 3)
        if e['estado'] in {'CON_NOVEDAD', 'RECHAZADA'} or e['cantidad_rechazada'] > 0 or abs(dif) > 0.001:
            novedades.append({
                'origen': 'ENTREGA_RECEPCION',
                'fecha': e['fecha_recepcion'] or e['fecha_entrega'],
                'sede': e['nombre_sede'],
                'referencia': e['documento_entrega'],
                'producto': e['nombre_ingrediente'],
                'detalle': (
                    f"Estado {e['estado']} | Despachado: {e['cantidad_despachada']} {e['unidad']}, "
                    f"Recibido: {e['cantidad_recibida']} {e['unidad']}, Rechazado: {e['cantidad_rechazada']} {e['unidad']}"
                    + (f" — Motivo: {e['motivo_rechazo']}" if e['motivo_rechazo'] else '')
                ),
                'severidad': 'ALTA' if e['estado'] == 'RECHAZADA' or e['cantidad_rechazada'] > 0 else 'MEDIA',
            })

    for inv in datos['inventario_rows']:
        if inv['estado_stock'] == 'Stock Crítico / Bajo Mínimo':
            novedades.append({
                'origen': 'INVENTARIO',
                'fecha': datos['fecha_actualizacion'][:10],
                'sede': inv['nombre_sede'],
                'referencia': f"INV-{inv['id_inventario']}",
                'producto': inv['nombre_ingrediente'],
                'detalle': f"Saldo actual {inv['cantidad_actual']} {inv['unidad']} <= stock mínimo {inv['stock_minimo']} {inv['unidad']}",
                'severidad': 'ALTA',
            })

    for al in datos['alertas_calculo']:
        novedades.append({
            'origen': 'PROGRAMACION_HU5',
            'fecha': datos['fecha_actualizacion'][:10],
            'sede': al.get('sede', ''),
            'referencia': al.get('tipo', 'ALERTA'),
            'producto': '-',
            'detalle': al.get('mensaje', ''),
            'severidad': 'ALTA' if al.get('nivel') == 'ERROR' else 'MEDIA',
        })

    for pln in planillas_qs.filter(estado__in=['OBSERVADO', 'BORRADOR']):
        novedades.append({
            'origen': 'PLANILLA_GENERADA',
            'fecha': pln.fecha_generacion.date().isoformat(),
            'sede': pln.id_sede.nombre_sede if pln.id_sede else 'Institucional',
            'referencia': pln.codigo_documento,
            'producto': pln.categoria_proceso,
            'detalle': pln.observaciones or f"Planilla en estado {pln.estado} con {len(pln.campos_pendientes or [])} campo(s) pendiente(s)",
            'severidad': 'MEDIA',
        })

    return novedades


def generar_reporte_consolidado(usuario, params: dict | None = None) -> dict:
    """
    SIR-173: Genera reportes operativos consolidados con datos 100% reales de SIRAE,
    acotados estrictamente a las instituciones/sedes/jornadas y reportes permitidos al rol.
    """
    params = params or {}
    tipos_disponibles = obtener_tipos_reporte_para_usuario(usuario)
    if not tipos_disponibles:
        raise PermissionDenied(
            "Tu rol operativo únicamente gestiona planillas de comedor y no tiene acceso a reportes consolidados."
        )

    codigos_permitidos = {t['codigo'] for t in tipos_disponibles}
    tipo_solicitado = (params.get('tipo_reporte') or '').strip().upper()
    if tipo_solicitado:
        if tipo_solicitado not in codigos_permitidos:
            raise PermissionDenied(
                f"Tu rol no está autorizado para consultar el reporte '{tipo_solicitado}'."
            )
        tipo = tipo_solicitado
    else:
        tipo = tipos_disponibles[0]['codigo']
    id_inst = params.get('id_institucion') or None
    id_sede = params.get('id_sede') or None
    id_jornada = params.get('id_jornada') or None
    id_contrato = params.get('id_contrato') or None
    fi = _parse_fecha(params.get('fecha_desde') or params.get('fecha_inicio'))
    ff = _parse_fecha(params.get('fecha_hasta') or params.get('fecha_fin'))

    datos = recopilar_datos_operativos_sirae(
        usuario,
        id_institucion=id_inst,
        id_sede=id_sede,
        id_jornada=id_jornada,
        id_contrato=id_contrato,
        fecha_desde=fi,
        fecha_fin=ff,
    )

    planillas_qs = PlanillaGenerada.objects.filter(
        id_institucion_id__in=datos['registros_origen']['institucion_ids']
    ).select_related('id_sede')
    if datos['registros_origen']['sede_ids']:
        from django.db.models import Q
        planillas_qs = planillas_qs.filter(
            Q(id_sede_id__in=datos['registros_origen']['sede_ids']) | Q(id_sede__isnull=True)
        )
    if fi:
        planillas_qs = planillas_qs.filter(fecha_generacion__date__gte=fi)
    if ff:
        planillas_qs = planillas_qs.filter(fecha_generacion__date__lte=ff)

    novedades_rows = _construir_filas_novedades(datos, planillas_qs)
    contratos_cupos_rows = _construir_filas_contratos_cupos(datos)
    comp = datos['comparativo_productos']

    detalle_por_tipo = {
        'RESUMEN_GENERAL': comp,
        'CONTRATOS_CUPOS': contratos_cupos_rows,
        'GRAMAJES_PROYECTADOS': datos['gramajes_rows'],
        'PROGRAMACION_ENTREGAS': datos['programacion_rows'] or datos['entregas_rows'],
        'RECEPCIONES_DIFERENCIAS': datos['recepciones_rows'],
        'INVENTARIO_CONSOLIDADO': datos['inventario_rows'],
        'MOVIMIENTOS_KARDEX': datos['kardex_rows'],
        'MENUS_PREPARACIONES': datos['preparaciones_rows'],
        'ASISTENCIA_GRADOS': datos['asistencia_rows'],
        'CONSUMO_ALIMENTOS': comp,
        'NOVEDADES_INCONSISTENCIAS': novedades_rows,
    }
    detalle = detalle_por_tipo.get(tipo, comp)

    totales_asistencia_cupos = datos['cupos']['total_cupos']
    cobertura_promedio = (
        round(
            sum(a['porcentaje_asistencia'] for a in datos['asistencia_rows']) / len(datos['asistencia_rows']),
            2,
        )
        if datos['asistencia_rows']
        else 0.0
    )

    resumen_ejecutivo = {
        'instituciones_autorizadas': len(datos['instituciones']),
        'sedes_autorizadas': len(datos['sedes']),
        'contratos_activos': sum(1 for c in datos['contratos'] if (c.estado or '').upper() == 'ACTIVO'),
        'total_contratos': len(datos['contratos']),
        'total_cupos': totales_asistencia_cupos,
        'total_entregas': len(datos['entregas_rows']),
        'entregas_recibidas': sum(1 for e in datos['entregas_rows'] if e['estado'] in {'RECIBIDA', 'CON_NOVEDAD'}),
        'entregas_con_novedad': sum(1 for e in datos['entregas_rows'] if e['estado'] in {'CON_NOVEDAD', 'RECHAZADA'}),
        'productos_programados': round(sum(r['cantidad_programada'] for r in comp), 3),
        'productos_despachados': round(sum(r['cantidad_despachada'] for r in comp), 3),
        'productos_recibidos': round(sum(r['cantidad_recibida'] for r in comp), 3),
        'productos_consumidos': round(sum(r['cantidad_consumida'] for r in comp), 3),
        'productos_bajo_minimo': datos['bajo_stock_count'],
        'total_movimientos_kardex': len(datos['kardex_rows']),
        'total_preparaciones': len(datos['preparaciones_rows']),
        'registros_asistencia': len(datos['asistencia_rows']),
        'asistencia_acumulada': datos['total_asistencia_reportada'],
        'cobertura_asistencia_promedio': cobertura_promedio,
        'total_novedades': len(novedades_rows),
        'planillas_generadas': planillas_qs.count(),
    }

    return {
        'tipo_reporte': tipo,
        'tipos_disponibles': tipos_disponibles,
        'filtros_aplicados': {
            'id_institucion': id_inst,
            'id_sede': id_sede,
            'id_jornada': id_jornada,
            'id_contrato': id_contrato,
            'fecha_desde': fi.isoformat() if fi else None,
            'fecha_hasta': ff.isoformat() if ff else None,
        },
        'permisos_usuario': {
            'rol': usuario_rol_canonico(usuario),
            'alcance': describir_alcance_usuario(usuario),
        },
        'fecha_actualizacion': datos['fecha_actualizacion'],
        'resumen_ejecutivo': resumen_ejecutivo,
        'comparativo_productos': comp,
        'consolidado_sedes': datos['consolidado_sedes'],
        'desagregado_grados': datos['cupos']['detalle_grados'],
        'detalle': detalle,
        'responsables': datos['responsables'],
        'registros_origen': datos['registros_origen'],
    }


def exportar_consolidado_csv(reporte: dict) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    resumen = reporte.get('resumen_ejecutivo') or {}
    writer.writerow(['SIRAE - REPORTE OPERATIVO CONSOLIDADO PAE'])
    writer.writerow(['Tipo reporte', reporte.get('tipo_reporte', '')])
    writer.writerow(['Rol', (reporte.get('permisos_usuario') or {}).get('rol', '')])
    writer.writerow(['Fecha actualización', reporte.get('fecha_actualizacion', '')])
    writer.writerow([])

    writer.writerow(['RESUMEN EJECUTIVO'])
    for k, v in resumen.items():
        writer.writerow([k, v])
    writer.writerow([])

    detalle = reporte.get('detalle') or []
    if detalle:
        writer.writerow(['DETALLE DEL REPORTE'])
        headers = list(detalle[0].keys())
        writer.writerow(headers)
        for row in detalle:
            writer.writerow([row.get(h, '') for h in headers])
    writer.writerow([])

    sedes = reporte.get('consolidado_sedes') or []
    if sedes:
        writer.writerow(['CONSOLIDADO MULTI-SEDE'])
        s_headers = list(sedes[0].keys())
        writer.writerow(s_headers)
        for row in sedes:
            writer.writerow([row.get(h, '') for h in s_headers])

    return '\ufeff' + buffer.getvalue()

