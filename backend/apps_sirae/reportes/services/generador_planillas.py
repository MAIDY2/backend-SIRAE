import csv
import io
from datetime import date, datetime

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps_sirae.reportes.models import PlanillaGenerada, PlantillaVersion
from apps_sirae.reportes.services.catalogo_fuentes import (
    aplicar_conversiones_y_formulas_filas,
    convertir_valor_unidad_sirae,
    evaluar_expresion_segura,
    usuario_autorizado_para_plantilla,
)
from apps_sirae.reportes.services.plantillas import obtener_version_publicada_para_proceso
from apps_sirae.reportes.services.recopilador_sirae import recopilar_datos_operativos_sirae


ESTADOS_TRANSICION_REVISION = {'BORRADOR', 'PENDIENTE', 'OBSERVADO', 'VALIDADO', 'CERRADO'}


def _parse_fecha(valor) -> date | None:
    if not valor:
        return None
    if isinstance(valor, date) and not isinstance(valor, datetime):
        return valor
    if isinstance(valor, datetime):
        return valor.date()
    try:
        return date.fromisoformat(str(valor).strip()[:10])
    except ValueError:
        return None


def _extraer_valor_campo(
    datos: dict,
    campo_def: dict,
    *,
    sede_obj=None,
    inst_obj=None,
    contrato_obj=None,
    jornada_obj=None,
    valores_manuales: dict | None = None,
) -> tuple[object, str | None]:
    """
    Resuelve el valor real de un campo definido en la plantilla (SIRAE o manual)
    y retorna (valor, motivo_pendiente_o_None).
    """
    valores_manuales = valores_manuales or {}
    codigo = campo_def.get('codigo') or ''
    origen = (campo_def.get('origen') or 'AUTOMATICO').upper()
    etiqueta = campo_def.get('etiqueta') or codigo

    if origen == 'MANUAL':
        val = valores_manuales.get(codigo)
        if val in (None, ''):
            if campo_def.get('requerido'):
                return 'PENDIENTE', f"Campo manual requerido sin diligenciar: {etiqueta}"
            return 'PENDIENTE', f"Campo manual opcional pendiente por diligenciar: {etiqueta}"
        return val, None

    fuente = (campo_def.get('fuente_sirae') or '').upper()
    campo = (campo_def.get('campo_fuente') or codigo).strip()

    val = None
    if fuente == 'INSTITUCION' and inst_obj:
        val = getattr(inst_obj, campo, None)
    elif fuente == 'SEDE' and sede_obj:
        val = getattr(sede_obj, campo, None)
    elif fuente == 'CONTRATO' and contrato_obj:
        if campo == 'operador':
            val = getattr(contrato_obj, 'institucion', None)
        else:
            val = getattr(contrato_obj, campo, None)
            if isinstance(val, date):
                val = val.isoformat()
    elif fuente == 'JORNADA' and jornada_obj:
        if campo == 'nombre_jornada':
            val = getattr(jornada_obj, 'nombre_jornada', None)
        elif campo == 'cupos_jornada':
            val = datos['cupos']['total_cupos']
    elif fuente == 'CUPOS_GRADOS':
        if campo == 'total_cupos':
            val = datos['cupos']['total_cupos']
        else:
            val = datos['cupos']['por_nivel'].get(campo)
    elif fuente == 'FIRMAS_USUARIOS':
        val = datos['responsables'].get(campo)
    elif fuente == 'ABASTECIMIENTO_CALCULO':
        if campo == 'dias_cobertura':
            val = datos.get('dias_cobertura_max') or None
    elif fuente == 'ASISTENCIA':
        if campo == 'total_asistencia':
            val = datos.get('total_asistencia_reportada') or None

    if val in (None, '', 'PENDIENTE'):
        return 'PENDIENTE', f"Información no disponible en módulo {fuente or 'SIRAE'} para '{etiqueta}'."

    if campo_def.get('unidad_destino') and isinstance(val, (int, float)):
        val, _, _ = convertir_valor_unidad_sirae(val, '', campo_def['unidad_destino'])
    return val, None


def _seleccionar_filas_fuente(datos: dict, fuente_sirae: str, categoria_proceso: str) -> tuple[list[dict], str]:
    ft = (fuente_sirae or categoria_proceso or '').upper()
    mapping = {
        'ABASTECIMIENTO_CALCULO': (datos['programacion_rows'] or datos['comparativo_productos'], 'Abastecimiento HU5'),
        'ENTREGAS': (datos['entregas_rows'], 'Entregas despachadas'),
        'RECEPCIONES': (datos['recepciones_rows'], 'Recepciones en sede'),
        'INVENTARIO': (datos['inventario_rows'], 'Inventario actual'),
        'KARDEX': (datos['kardex_rows'], 'Movimientos kárdex'),
        'ASISTENCIA': (datos['asistencia_rows'], 'Asistencia diaria'),
        'PREPARACIONES': (datos['preparaciones_rows'], 'Preparaciones y minutas'),
        'MENUS_RECETAS': (datos['preparaciones_rows'], 'Menús y recetas'),
        'GRAMAJES': (datos['gramajes_rows'], 'Gramajes nutricionales'),
        'CUPOS_GRADOS': (datos['cupos']['detalle_grados'], 'Cupos por grados'),
        'CONSUMO': (datos['comparativo_productos'], 'Balance comparativo de consumo'),
        'REMISION': (datos['comparativo_productos'], 'Balance de remisión y despacho'),
    }
    if ft in mapping:
        filas, nombre = mapping[ft]
        return [dict(r) for r in filas], nombre
    return [dict(r) for r in datos['comparativo_productos']], 'Datos operativos SIRAE'


def _construir_snapshot_desde_version(
    version: PlantillaVersion,
    usuario,
    *,
    id_institucion=None,
    id_sede=None,
    id_contrato=None,
    id_jornada=None,
    periodo: str = '',
    fecha_inicio: date | None = None,
    fecha_fin: date | None = None,
    valores_manuales: dict | None = None,
    permitir_sin_sede: bool = False,
) -> dict:
    plantilla = version.id_plantilla
    datos = recopilar_datos_operativos_sirae(
        usuario,
        id_institucion=id_institucion,
        id_sede=id_sede,
        id_jornada=id_jornada,
        id_contrato=id_contrato,
        fecha_desde=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    sedes = datos['sedes']
    instituciones = datos['instituciones']
    contratos = datos['contratos']

    sede_obj = sedes[0] if (id_sede or len(sedes) == 1) and sedes else None
    inst_obj = (
        sede_obj.id_institucion
        if (sede_obj and sede_obj.id_institucion)
        else (instituciones[0] if instituciones else None)
    )
    contrato_obj = None
    if id_contrato:
        contrato_obj = next((c for c in contratos if c.id_contrato == int(id_contrato)), None)
    if contrato_obj is None and contratos:
        contrato_obj = contratos[0]

    if not inst_obj and not permitir_sin_sede:
        raise ValidationError("No se encontró una institución educativa autorizada para generar el documento.")

    jornada_obj = None
    if id_jornada:
        from apps_sirae.jornadas.models import Jornada
        jornada_obj = Jornada.objects.filter(id_jornada=id_jornada).first()

    esquema = version.esquema or {}
    campos_resueltos = []
    campos_pendientes = []
    contexto_formulas = {}

    for cmp_def in esquema.get('campos') or []:
        valor, motivo_pend = _extraer_valor_campo(
            datos,
            cmp_def,
            sede_obj=sede_obj,
            inst_obj=inst_obj,
            contrato_obj=contrato_obj,
            jornada_obj=jornada_obj,
            valores_manuales=valores_manuales,
        )
        if cmp_def.get('formula') and cmp_def.get('origen') != 'MANUAL':
            valor = evaluar_expresion_segura(cmp_def['formula'], contexto_formulas)
            motivo_pend = None
        if isinstance(valor, (int, float)):
            contexto_formulas[cmp_def.get('codigo', '')] = valor

        esta_pendiente = valor == 'PENDIENTE'
        if esta_pendiente and motivo_pend:
            campos_pendientes.append({
                'tipo': 'CAMPO',
                'codigo': cmp_def.get('codigo'),
                'etiqueta': cmp_def.get('etiqueta'),
                'origen': cmp_def.get('origen', 'AUTOMATICO'),
                'motivo': motivo_pend,
            })

        campos_resueltos.append({
            'codigo': cmp_def.get('codigo'),
            'etiqueta': cmp_def.get('etiqueta'),
            'seccion': cmp_def.get('seccion'),
            'tipo': cmp_def.get('tipo', 'TEXTO'),
            'origen': cmp_def.get('origen', 'AUTOMATICO'),
            'fuente_sirae': cmp_def.get('fuente_sirae', ''),
            'valor': valor,
            'pendiente': esta_pendiente,
            'requerido': bool(cmp_def.get('requerido', False)),
        })

    tablas_resueltas = []
    advertencias_conversion = []
    manuales_tablas = (valores_manuales or {}).get('__tablas__') or {}

    for tbl_def in esquema.get('tablas') or []:
        cod_tbl = tbl_def.get('codigo') or 'TABLA'
        filas_base, nombre_fuente = _seleccionar_filas_fuente(
            datos,
            tbl_def.get('fuente_sirae') or '',
            plantilla.categoria_proceso,
        )
        # Combinar columnas manuales por fila si el usuario las editó
        edits_tbl = manuales_tablas.get(cod_tbl) or {}
        if isinstance(edits_tbl, dict) and filas_base:
            for idx_row, row in enumerate(filas_base):
                row_edits = edits_tbl.get(str(idx_row))
                if isinstance(row_edits, dict):
                    row.update(row_edits)

        filas_proc, totales_tbl, advs = aplicar_conversiones_y_formulas_filas(
            tbl_def,
            filas_base,
            ingredientes_by_id=datos['ingredientes_by_id'],
        )
        advertencias_conversion.extend(advs)

        if not filas_proc:
            campos_pendientes.append({
                'tipo': 'TABLA',
                'codigo': cod_tbl,
                'etiqueta': tbl_def.get('titulo') or cod_tbl,
                'origen': 'AUTOMATICO',
                'motivo': f"Sin registros en fuente '{nombre_fuente}' para el ámbito y periodo seleccionados.",
            })

        tablas_resueltas.append({
            'codigo': cod_tbl,
            'titulo': tbl_def.get('titulo') or cod_tbl,
            'seccion': tbl_def.get('seccion') or '',
            'fuente_sirae': tbl_def.get('fuente_sirae') or '',
            'columnas': tbl_def.get('columnas') or [],
            'filas': filas_proc,
            'totales': totales_tbl,
            'pendiente': len(filas_proc) == 0,
        })

    # Resumen comparativo transversal (SIR-171 criterio: diferenciar programado, despachado, recibido y consumido)
    comp = datos['comparativo_productos']
    totales_cadena = {
        'productos_count': len(comp),
        'total_programado': round(sum(r['cantidad_programada'] for r in comp), 3),
        'total_despachado': round(sum(r['cantidad_despachada'] for r in comp), 3),
        'total_recibido': round(sum(r['cantidad_recibida'] for r in comp), 3),
        'total_consumido': round(sum(r['cantidad_consumida'] for r in comp), 3),
        'total_cupos': datos['cupos']['total_cupos'],
        'total_asistencia': datos['total_asistencia_reportada'],
        'dias_cobertura_max': datos['dias_cobertura_max'],
    }

    # Determinar estado inicial real (SIR-171)
    hay_pendientes_reales = bool(campos_pendientes)
    estado_sugerido = 'BORRADOR' if hay_pendientes_reales else 'PENDIENTE'

    snapshot = {
        'encabezado': {
            **(esquema.get('encabezado') or {}),
            'plantilla_codigo': plantilla.codigo,
            'plantilla_nombre': plantilla.nombre,
            'version_numero': version.numero_version,
            'version_estado': version.estado,
            'categoria_proceso': plantilla.categoria_proceso,
            'periodo': periodo,
            'fecha_inicio': fecha_inicio.isoformat() if fecha_inicio else '',
            'fecha_fin': fecha_fin.isoformat() if fecha_fin else '',
            'institucion': {
                'id_institucion': inst_obj.id_institucion if inst_obj else None,
                'nombre': inst_obj.nombre_institucion if inst_obj else 'Ámbito sin institución',
                'nit': getattr(inst_obj, 'nit', '') if inst_obj else '',
            },
            'sede': {
                'id_sede': sede_obj.id_sede if sede_obj else None,
                'nombre': sede_obj.nombre_sede if sede_obj else 'Consolidado institucional',
                'codigo_dane': getattr(sede_obj, 'codigo_dane', '') if sede_obj else '',
                'direccion': getattr(sede_obj, 'direccion', '') if sede_obj else '',
            },
            'contrato': {
                'id_contrato': contrato_obj.id_contrato if contrato_obj else None,
                'numero_cor': contrato_obj.numero_cor if contrato_obj else 'PENDIENTE',
                'operador': contrato_obj.institucion if contrato_obj else 'PENDIENTE',
                'zona': contrato_obj.zona if contrato_obj else '',
            },
            'jornada': {
                'id_jornada': jornada_obj.id_jornada if jornada_obj else None,
                'nombre': jornada_obj.nombre_jornada if jornada_obj else 'Todas las jornadas',
            },
        },
        'secciones': esquema.get('secciones') or [],
        'campos': campos_resueltos,
        'tablas': tablas_resueltas,
        'cupos': {
            'total_cupos': datos['cupos']['total_cupos'],
            'por_nivel': datos['cupos']['por_nivel'],
            'detalle_grados': datos['cupos']['detalle_grados'],
        },
        'comparativo_productos': comp,
        'totales_cadena': totales_cadena,
        'responsables': {
            'supervisor': datos['responsables']['supervisor_nombre'],
            'administrador_institucional': datos['responsables']['administrador_nombre'],
            'jefa_manipuladoras': datos['responsables']['jefa_cocina_nombre'],
            'generado_por': getattr(usuario, 'nombre_completo', '') or str(usuario),
        },
        'alertas_conversion': advertencias_conversion,
        'alertas_configuracion': datos['alertas_calculo'],
    }

    return {
        'inst_obj': inst_obj,
        'sede_obj': sede_obj,
        'contrato_obj': contrato_obj,
        'jornada_obj': jornada_obj,
        'snapshot': snapshot,
        'campos_pendientes': campos_pendientes,
        'registros_origen': datos['registros_origen'],
        'estado_sugerido': estado_sugerido,
    }


def previsualizar_version_plantilla(version: PlantillaVersion, usuario, params: dict | None = None) -> dict:
    """
    SIR-170: Previsualización en vivo de la plantilla antes de publicarla.
    Si el usuario indica `id_sede` o `id_institucion`, la previsualiza con datos reales de SIRAE;
    en caso contrario, retorna la estructura completa con sus fuentes y fórmulas configuradas.
    """
    params = params or {}
    id_inst = params.get('id_institucion')
    id_sede = params.get('id_sede')
    id_contrato = params.get('id_contrato')
    id_jornada = params.get('id_jornada')
    fi = _parse_fecha(params.get('fecha_inicio'))
    ff = _parse_fecha(params.get('fecha_fin'))
    periodo = (params.get('periodo') or f'{fi.isoformat() if fi else "ACTUAL"}').strip()

    res = _construir_snapshot_desde_version(
        version,
        usuario,
        id_institucion=id_inst,
        id_sede=id_sede,
        id_contrato=id_contrato,
        id_jornada=id_jornada,
        periodo=periodo,
        fecha_inicio=fi,
        fecha_fin=ff,
        permitir_sin_sede=True,
    )
    return {
        'id_plantilla': version.id_plantilla_id,
        'id_version': version.id_version,
        'numero_version': version.numero_version,
        'estado_version': version.estado,
        'es_inmutable': version.es_inmutable(),
        'estado_documento_estimado': res['estado_sugerido'],
        'campos_pendientes': res['campos_pendientes'],
        'preview': res['snapshot'],
    }


def _construir_clave_unicidad(
    *,
    id_plantilla: int,
    categoria_proceso: str,
    id_institucion: int,
    id_sede: int | None,
    id_jornada: int | None,
    periodo: str,
    fecha_inicio: date | None,
    fecha_fin: date | None,
) -> str:
    per_norm = ' '.join((periodo or 'GENERAL').strip().upper().split())[:40]
    fi = fecha_inicio.isoformat() if fecha_inicio else 'NONE'
    ff = fecha_fin.isoformat() if fecha_fin else 'NONE'
    return (
        f"P{id_plantilla}|PROC:{categoria_proceso}|INST:{id_institucion}|"
        f"SEDE:{id_sede or 0}|JOR:{id_jornada or 0}|PER:{per_norm}|INI:{fi}|FIN:{ff}"
    )


def generar_planilla_automatica(usuario, payload: dict) -> tuple[PlanillaGenerada, bool]:
    """
    SIR-171: Genera y diligencia automáticamente la planilla a partir de datos reales en BD.
    Evita duplicados para el mismo proceso, plantilla, sede, jornada y periodo.
    Retorna (planilla, creada_o_regenerada).
    """
    id_plantilla = payload.get('id_plantilla')
    categoria = (payload.get('categoria_proceso') or '').strip().upper()
    version = obtener_version_publicada_para_proceso(
        usuario,
        id_plantilla=id_plantilla,
        categoria_proceso=categoria,
    )
    plantilla = version.id_plantilla

    id_institucion = payload.get('id_institucion')
    id_sede = payload.get('id_sede')
    id_contrato = payload.get('id_contrato')
    id_jornada = payload.get('id_jornada')
    fecha_inicio = _parse_fecha(payload.get('fecha_inicio'))
    fecha_fin = _parse_fecha(payload.get('fecha_fin'))
    periodo = (payload.get('periodo') or '').strip()
    if not periodo:
        if fecha_inicio and fecha_fin:
            periodo = f"{fecha_inicio.isoformat()} a {fecha_fin.isoformat()}"
        elif fecha_inicio:
            periodo = fecha_inicio.strftime('%Y-%m')
        else:
            periodo = timezone.localdate().strftime('%Y-%m')

    valores_manuales = payload.get('valores_manuales') if isinstance(payload.get('valores_manuales'), dict) else {}
    regenerar = bool(payload.get('regenerar', False))
    permitir_existente = bool(payload.get('reutilizar_existente', False))
    evento_origen = (payload.get('evento_origen') or 'GENERACION_MANUAL_DESDE_DATOS').strip()

    evaluacion = _construir_snapshot_desde_version(
        version,
        usuario,
        id_institucion=id_institucion,
        id_sede=id_sede,
        id_contrato=id_contrato,
        id_jornada=id_jornada,
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        valores_manuales=valores_manuales,
        permitir_sin_sede=False,
    )
    inst_obj = evaluacion['inst_obj']
    sede_obj = evaluacion['sede_obj']
    contrato_obj = evaluacion['contrato_obj']
    jornada_obj = evaluacion['jornada_obj']

    clave = _construir_clave_unicidad(
        id_plantilla=plantilla.id_plantilla,
        categoria_proceso=plantilla.categoria_proceso,
        id_institucion=inst_obj.id_institucion,
        id_sede=sede_obj.id_sede if sede_obj else None,
        id_jornada=jornada_obj.id_jornada if jornada_obj else None,
        periodo=periodo,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
    )

    existente = PlanillaGenerada.objects.filter(clave_unicidad=clave).first()
    if existente:
        if not regenerar:
            if permitir_existente:
                return existente, False
            raise ValidationError(
                f"Ya existe un documento generado ({existente.codigo_documento}) para el mismo proceso, "
                f"sede, jornada y periodo ({periodo}). Consulte el documento existente o utilice regenerar borrador."
            )
        if existente.estado in {'VALIDADO', 'CERRADO'}:
            raise ValidationError(
                f"El documento {existente.codigo_documento} ya se encuentra en estado {existente.estado} y no puede sobrescribirse."
            )

    sufijo_sede = sede_obj.id_sede if sede_obj else f"I{inst_obj.id_institucion}"
    nombre_doc = (payload.get('nombre_documento') or '').strip() or (
        f"{plantilla.nombre} - {sede_obj.nombre_sede if sede_obj else inst_obj.nombre_institucion} ({periodo})"
    )

    with transaction.atomic():
        if existente and regenerar:
            existente.id_plantilla_version = version
            existente.nombre_documento = nombre_doc[:200]
            existente.id_contrato = contrato_obj
            existente.estado = evaluacion['estado_sugerido']
            existente.evento_origen = evento_origen[:80]
            existente.responsable_generacion = usuario
            existente.responsable_nombre = getattr(usuario, 'nombre_completo', '') or str(usuario)
            existente.contenido_snapshot = evaluacion['snapshot']
            existente.valores_manuales = valores_manuales
            existente.campos_pendientes = evaluacion['campos_pendientes']
            existente.registros_origen = evaluacion['registros_origen']
            existente.observaciones = (payload.get('observaciones') or existente.observaciones or '').strip()
            existente.save()
            return existente, True

        stamp = timezone.now().strftime('%Y%m%d%H%M%S%f')[-10:]
        codigo_doc = f"PLN-{plantilla.categoria_proceso[:4]}-{sufijo_sede}-{stamp}"
        planilla = PlanillaGenerada.objects.create(
            codigo_documento=codigo_doc[:60],
            id_plantilla_version=version,
            nombre_documento=nombre_doc[:200],
            categoria_proceso=plantilla.categoria_proceso,
            id_institucion=inst_obj,
            id_sede=sede_obj,
            id_contrato=contrato_obj,
            id_jornada=jornada_obj,
            periodo=periodo[:80],
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            clave_unicidad=clave,
            estado=evaluacion['estado_sugerido'],
            evento_origen=evento_origen[:80],
            responsable_generacion=usuario,
            responsable_nombre=(getattr(usuario, 'nombre_completo', '') or str(usuario))[:200],
            contenido_snapshot=evaluacion['snapshot'],
            valores_manuales=valores_manuales,
            campos_pendientes=evaluacion['campos_pendientes'],
            registros_origen=evaluacion['registros_origen'],
            observaciones=(payload.get('observaciones') or '').strip(),
        )
    return planilla, True


def actualizar_planilla_y_manuales(planilla: PlanillaGenerada, usuario, data: dict) -> PlanillaGenerada:
    """
    Actualiza campos manuales, observaciones o estado operativo de una planilla existente
    conservando la versión exacta de la plantilla original (inmutabilidad histórica).
    """
    if planilla.estado == 'CERRADO':
        raise ValidationError("El documento está CERRADO y no admite modificaciones posteriores.")

    plantilla = planilla.id_plantilla_version.id_plantilla
    if not usuario_autorizado_para_plantilla(usuario, plantilla):
        raise ValidationError("Su rol no está autorizado para modificar documentos de esta plantilla.")

    if 'valores_manuales' in data:
        nuevos_manuales = data.get('valores_manuales')
        if not isinstance(nuevos_manuales, dict):
            raise ValidationError("Los valores manuales deben enviarse como objeto JSON.")
        combinados = {**(planilla.valores_manuales or {}), **nuevos_manuales}
        planilla.valores_manuales = combinados

        # Reevaluar snapshot usando exactamente la MISMA versión histórica de plantilla
        evaluacion = _construir_snapshot_desde_version(
            planilla.id_plantilla_version,
            usuario,
            id_institucion=planilla.id_institucion_id,
            id_sede=planilla.id_sede_id,
            id_contrato=planilla.id_contrato_id,
            id_jornada=planilla.id_jornada_id,
            periodo=planilla.periodo,
            fecha_inicio=planilla.fecha_inicio,
            fecha_fin=planilla.fecha_fin,
            valores_manuales=combinados,
            permitir_sin_sede=True,
        )
        planilla.contenido_snapshot = evaluacion['snapshot']
        planilla.campos_pendientes = evaluacion['campos_pendientes']
        if planilla.estado in {'BORRADOR', 'PENDIENTE'} and 'estado' not in data:
            planilla.estado = evaluacion['estado_sugerido']

    if 'observaciones' in data:
        planilla.observaciones = (data.get('observaciones') or '').strip()

    if 'estado' in data and data['estado']:
        nuevo_estado = str(data['estado']).strip().upper()
        if nuevo_estado not in ESTADOS_TRANSICION_REVISION:
            raise ValidationError(f"Estado '{nuevo_estado}' no válido.")
        if nuevo_estado == 'CERRADO' and planilla.campos_pendientes:
            # Permitir cerrar únicamente si todos los campos obligatorios fueron resueltos o con observación explícita
            pend_req = [
                c for c in planilla.campos_pendientes
                if c.get('tipo') == 'CAMPO'
            ]
            if pend_req and not (planilla.observaciones or '').strip():
                raise ValidationError(
                    "Existen campos pendientes; registre una observación explicativa antes de cerrar el documento."
                )
        planilla.estado = nuevo_estado
        if nuevo_estado in {'OBSERVADO', 'VALIDADO', 'CERRADO'}:
            planilla.revisado_por = usuario
            planilla.fecha_revision = timezone.now()

    planilla.save()
    return planilla


def exportar_planilla_csv(planilla: PlanillaGenerada) -> str:
    """
    SIR-172: Genera representación CSV descargable del documento completo con trazabilidad.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    snap = planilla.contenido_snapshot or {}
    enc = snap.get('encabezado') or {}

    writer.writerow(['SIRAE - PLANILLA OFICIAL PAE'])
    writer.writerow(['Código documento', planilla.codigo_documento])
    writer.writerow(['Nombre documento', planilla.nombre_documento])
    writer.writerow(['Proceso', planilla.categoria_proceso])
    writer.writerow(['Plantilla / Versión', f"{enc.get('plantilla_codigo', '')} v{enc.get('version_numero', '')}"])
    writer.writerow(['Estado', planilla.estado])
    writer.writerow(['Institución', (enc.get('institucion') or {}).get('nombre', '')])
    writer.writerow(['Sede', (enc.get('sede') or {}).get('nombre', '')])
    writer.writerow(['Contrato', (enc.get('contrato') or {}).get('numero_cor', '')])
    writer.writerow(['Periodo', planilla.periodo])
    writer.writerow(['Fecha generación', planilla.fecha_generacion.isoformat()])
    writer.writerow(['Generado por', planilla.responsable_nombre])
    writer.writerow([])

    campos = snap.get('campos') or []
    if campos:
        writer.writerow(['CAMPOS DE ENCABEZADO Y METADATOS'])
        writer.writerow(['Etiqueta', 'Origen', 'Fuente', 'Valor'])
        for c in campos:
            writer.writerow([c.get('etiqueta', ''), c.get('origen', ''), c.get('fuente_sirae', ''), c.get('valor', '')])
        writer.writerow([])

    for tbl in snap.get('tablas') or []:
        writer.writerow([f"TABLA: {tbl.get('titulo', '')}"])
        cols = tbl.get('columnas') or []
        writer.writerow([col.get('etiqueta', col.get('codigo', '')) for col in cols])
        for row in tbl.get('filas') or []:
            writer.writerow([row.get(col.get('codigo', ''), '') for col in cols])
        totales = tbl.get('totales') or {}
        if totales:
            writer.writerow([
                ('TOTALES' if idx == 0 else totales.get(col.get('codigo', ''), ''))
                for idx, col in enumerate(cols)
            ])
        writer.writerow([])

    resp = snap.get('responsables') or {}
    writer.writerow(['RESPONSABLES SIRAE'])
    writer.writerow(['Supervisor asignado', resp.get('supervisor', '')])
    writer.writerow(['Administrador institucional', resp.get('administrador_institucional', '')])
    writer.writerow(['Jefa de manipuladoras', resp.get('jefa_manipuladoras', '')])
    writer.writerow(['Registros origen', str(planilla.registros_origen or {})])

    return '\ufeff' + buffer.getvalue()
