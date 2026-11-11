import ast
from decimal import Decimal, InvalidOperation
import unicodedata

from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.unidades_medida.services import ErrorConversionUnidad, convertir_cantidad


PROCESOS_PAE = [
    {'codigo': 'REMISION', 'nombre': 'Remisión de alimentos y víveres', 'descripcion': 'Despacho y entrega de víveres por contrato, sede y periodo.'},
    {'codigo': 'RECEPCION', 'nombre': 'Recepción y verificación de alimentos', 'descripcion': 'Verificación en comedor escolar, cantidades recibidas, rechazadas y novedades.'},
    {'codigo': 'INVENTARIO', 'nombre': 'Control de inventario y kárdex', 'descripcion': 'Saldos actuales, entradas, salidas a cocina y alertas de stock mínimo.'},
    {'codigo': 'ASISTENCIA', 'nombre': 'Registro de asistencia diaria', 'descripcion': 'Asistencia diaria por grado escolar frente a cupos atendidos.'},
    {'codigo': 'PREPARACION', 'nombre': 'Preparación de alimentos y minutas', 'descripcion': 'Menús programados, platos, recetas y estado de preparaciones.'},
    {'codigo': 'CONSUMO', 'nombre': 'Consumo y balance operativo PAE', 'descripcion': 'Comparativo programado, despachado, recibido y consumido por producto y sede.'},
    {'codigo': 'MINUTA', 'nombre': 'Minuta y programación de menús', 'descripcion': 'Programación nutricional de menús, componentes e ingredientes base.'},
    {'codigo': 'OTRO', 'nombre': 'Otro formato oficial PAE', 'descripcion': 'Formato parametrizable para seguimiento institucional.'},
]

ROLES_PLANTILLA_CANONICOS = [
    {'codigo': 'SuperAdministrador', 'nombre': 'Super Administrador'},
    {'codigo': 'supervisor', 'nombre': 'Supervisor / Coordinador PAE'},
    {'codigo': 'Administrador', 'nombre': 'Administrador Institucional'},
    {'codigo': 'JefaManipuladoras', 'nombre': 'Jefa de Manipuladoras'},
    {'codigo': 'Manipuladora', 'nombre': 'Manipuladora de Alimentos'},
]

_ALIAS_ROL = {
    'superadministrador': 'SuperAdministrador',
    'super administrador': 'SuperAdministrador',
    'super admin': 'SuperAdministrador',
    'supervisor': 'supervisor',
    'supervisor pae': 'supervisor',
    'coordinador': 'supervisor',
    'coordinador pae': 'supervisor',
    'administrador': 'Administrador',
    'admin': 'Administrador',
    'administrador institucional': 'Administrador',
    'jefamanipuladoras': 'JefaManipuladoras',
    'jefa de manipuladoras': 'JefaManipuladoras',
    'jefa manipuladoras': 'JefaManipuladoras',
    'manipuladora': 'Manipuladora',
    'manipuladora de alimentos': 'Manipuladora',
}

FUENTES_SIRAE = [
    {
        'codigo': 'INSTITUCION',
        'nombre': 'Institución educativa',
        'campos': ['nombre_institucion', 'nit', 'representante_legal', 'telefono', 'correo_contacto', 'estado'],
    },
    {
        'codigo': 'SEDE',
        'nombre': 'Sede escolar',
        'campos': ['nombre_sede', 'codigo_dane', 'direccion', 'telefono', 'estado'],
    },
    {
        'codigo': 'CONTRATO',
        'nombre': 'Contrato PAE',
        'campos': ['numero_cor', 'operador', 'zona', 'fecha_inicio', 'fecha_fin', 'cupos', 'dias_cobertura_perecederos', 'dias_cobertura_no_perecederos'],
    },
    {
        'codigo': 'JORNADA',
        'nombre': 'Jornada escolar',
        'campos': ['nombre_jornada', 'cupos_jornada'],
    },
    {
        'codigo': 'CUPOS_GRADOS',
        'nombre': 'Cupos por grados y niveles',
        'campos': ['nombre_grado', 'nivel_educativo', 'nombre_grupo_gramaje', 'cupos'],
    },
    {
        'codigo': 'GRAMAJES',
        'nombre': 'Gramajes nutricionales',
        'campos': ['nombre_ingrediente', 'nombre_grado', 'cantidad_gramaje', 'unidad_medida', 'contexto_aplicacion'],
    },
    {
        'codigo': 'ABASTECIMIENTO_CALCULO',
        'nombre': 'Cálculo HU5 de abastecimiento',
        'campos': ['codigo_documento', 'nombre_ingrediente', 'tipo_conservacion', 'gramaje_por_racion', 'cantidad_programada', 'unidad', 'dias_cobertura'],
    },
    {
        'codigo': 'ENTREGAS',
        'nombre': 'Despachos y entregas',
        'campos': ['documento_entrega', 'fecha_entrega', 'nombre_ingrediente', 'cantidad_despachada', 'unidad', 'frecuencia', 'estado'],
    },
    {
        'codigo': 'RECEPCIONES',
        'nombre': 'Recepción y aprobación en sede',
        'campos': ['fecha_recepcion', 'nombre_ingrediente', 'cantidad_recibida', 'cantidad_rechazada', 'motivo_rechazo', 'observaciones', 'estado'],
    },
    {
        'codigo': 'INVENTARIO',
        'nombre': 'Inventario actual de sede',
        'campos': ['nombre_ingrediente', 'categoria', 'cantidad_actual', 'stock_minimo', 'unidad', 'estado_stock'],
    },
    {
        'codigo': 'KARDEX',
        'nombre': 'Movimientos kárdex (entradas y salidas)',
        'campos': ['fecha', 'tipo_movimiento', 'nombre_ingrediente', 'cantidad', 'unidad', 'usuario_responsable', 'observaciones'],
    },
    {
        'codigo': 'MENUS_RECETAS',
        'nombre': 'Menús y componentes de receta',
        'campos': ['fecha', 'nombre_jornada', 'nombre_plato', 'componente', 'nombre_ingrediente', 'porcion_por_nino', 'total_a_preparar'],
    },
    {
        'codigo': 'PREPARACIONES',
        'nombre': 'Preparaciones asignadas en cocina',
        'campos': ['fecha', 'hora_programada', 'nombre_plato', 'nombre_turno', 'responsable_cocina', 'estado_preparacion', 'observaciones'],
    },
    {
        'codigo': 'ASISTENCIA',
        'nombre': 'Asistencia diaria por grado',
        'campos': ['fecha', 'nombre_grado', 'cupos_grado', 'ninos_presentes', 'porcentaje_asistencia'],
    },
    {
        'codigo': 'CONSUMO',
        'nombre': 'Consumo y balance operativo',
        'campos': ['nombre_ingrediente', 'cantidad_programada', 'cantidad_despachada', 'cantidad_recibida', 'cantidad_consumida', 'unidad'],
    },
    {
        'codigo': 'FIRMAS_USUARIOS',
        'nombre': 'Responsables reales asignados en SIRAE',
        'campos': ['supervisor_nombre', 'administrador_nombre', 'jefa_cocina_nombre', 'responsable_generacion'],
    },
]


def _texto_normalizado(valor: str) -> str:
    crudo = (valor or '').strip()
    sin_tildes = ''.join(
        c for c in unicodedata.normalize('NFD', crudo)
        if unicodedata.category(c) != 'Mn'
    )
    return ' '.join(sin_tildes.lower().split())


def normalizar_rol_canonico(rol_valor: str) -> str:
    clave = _texto_normalizado(rol_valor)
    return _ALIAS_ROL.get(clave, (rol_valor or '').strip())


def normalizar_roles_lista(roles) -> list[str]:
    if not roles:
        return ['SuperAdministrador', 'supervisor', 'Administrador']
    resultado = []
    for item in roles:
        canon = normalizar_rol_canonico(str(item))
        if canon and canon not in resultado:
            resultado.append(canon)
    return resultado


def usuario_rol_canonico(usuario) -> str:
    if not usuario or not getattr(usuario, 'is_authenticated', False):
        return ''
    if getattr(usuario, 'es_super_administrador', lambda: False)():
        return 'SuperAdministrador'
    if getattr(usuario, 'es_supervisor', lambda: False)():
        return 'supervisor'
    if getattr(usuario, 'es_administrador', lambda: False)():
        return 'Administrador'
    if getattr(usuario, 'es_jefa_manipuladoras', lambda: False)():
        return 'JefaManipuladoras'
    if getattr(usuario, 'es_manipuladora', lambda: False)():
        return 'Manipuladora'
    rol_obj = getattr(usuario, 'rol', None)
    return normalizar_rol_canonico(getattr(rol_obj, 'nombre', '') or '')


def usuario_autorizado_para_plantilla(usuario, plantilla) -> bool:
    if getattr(usuario, 'es_super_administrador', lambda: False)():
        return True
    rol_usuario = usuario_rol_canonico(usuario)
    if not rol_usuario:
        return False
    roles_cfg = normalizar_roles_lista(getattr(plantilla, 'roles_autorizados', None))
    return rol_usuario in roles_cfg


def _a_decimal(valor, default=Decimal('0')):
    if valor is None or valor == '':
        return default
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _evaluar_nodo_ast(nodo, contexto: dict[str, Decimal]) -> Decimal:
    if isinstance(nodo, ast.Expression):
        return _evaluar_nodo_ast(nodo.body, contexto)
    if isinstance(nodo, ast.Constant):
        if isinstance(nodo.value, (int, float)):
            return _a_decimal(nodo.value)
        raise ValueError("Constante no numérica en fórmula")
    if isinstance(nodo, ast.Name):
        if nodo.id in contexto:
            return _a_decimal(contexto[nodo.id])
        return Decimal('0')
    if isinstance(nodo, ast.UnaryOp):
        val = _evaluar_nodo_ast(nodo.operand, contexto)
        if isinstance(nodo.op, ast.UAdd):
            return val
        if isinstance(nodo.op, ast.USub):
            return -val
        raise ValueError("Operador unario no permitido")
    if isinstance(nodo, ast.BinOp):
        izq = _evaluar_nodo_ast(nodo.left, contexto)
        der = _evaluar_nodo_ast(nodo.right, contexto)
        if isinstance(nodo.op, ast.Add):
            return izq + der
        if isinstance(nodo.op, ast.Sub):
            return izq - der
        if isinstance(nodo.op, ast.Mult):
            return izq * der
        if isinstance(nodo.op, ast.Div):
            if der == 0:
                return Decimal('0')
            return izq / der
        raise ValueError("Operador binario no permitido")
    raise ValueError("Expresión de fórmula no soportada")


def evaluar_expresion_segura(expresion: str, contexto: dict) -> float:
    """
    Evalúa expresiones aritméticas de columnas (ej: 'cantidad_recibida - cantidad_despachada',
    '(ninos_presentes / cupos_grado) * 100') sin ejecutar código arbitrario.
    """
    if not expresion or not isinstance(expresion, str):
        return 0.0
    ctx_dec = {
        str(k): _a_decimal(v)
        for k, v in (contexto or {}).items()
        if isinstance(v, (int, float, Decimal)) or (isinstance(v, str) and v.strip().replace('.', '', 1).replace('-', '', 1).isdigit())
    }
    try:
        arbol = ast.parse(expresion.strip(), mode='eval')
        resultado = _evaluar_nodo_ast(arbol, ctx_dec)
        return float(round(resultado, 3))
    except Exception:
        return 0.0


def _resolver_unidad_por_abreviatura(abrev: str):
    clave = (abrev or '').strip().lower()
    if not clave:
        return None
    alias_abrev = {
        'gr': 'g',
        'grs': 'g',
        'gramo': 'g',
        'gramos': 'g',
        'kilo': 'kg',
        'kilos': 'kg',
        'kilogramo': 'kg',
        'kilogramos': 'kg',
        'litro': 'l',
        'litros': 'l',
        'ml': 'ml',
        'und': 'und',
        'unidad': 'und',
        'unidades': 'und',
        'lb': 'lb',
        'libra': 'lb',
        'libras': 'lb',
    }
    buscada = alias_abrev.get(clave, clave)
    unidades = UnidadMedida.objects.filter(estado='ACTIVO')
    for u in unidades:
        if (u.abreviatura or '').strip().lower() == buscada or (u.nombre or '').strip().lower() == buscada:
            return u
    return None


def convertir_valor_unidad_sirae(
    cantidad,
    unidad_origen_str: str,
    unidad_destino_str: str,
    ingrediente=None,
) -> tuple[float, str, str]:
    """
    Reutiliza el servicio oficial de unidades_medida de SIRAE para convertir cantidades
    cuando el catálogo de unidades lo soporta. Retorna (cantidad_convertida, unidad_final, nota).
    """
    val = _a_decimal(cantidad)
    origen_txt = (unidad_origen_str or '').strip()
    destino_txt = (unidad_destino_str or '').strip()
    if not destino_txt or not origen_txt or origen_txt.lower() == destino_txt.lower():
        return float(round(val, 3)), destino_txt or origen_txt, ''

    u_ori = _resolver_unidad_por_abreviatura(origen_txt)
    u_des = _resolver_unidad_por_abreviatura(destino_txt)
    if u_ori and u_des:
        try:
            convertida = convertir_cantidad(val, u_ori, u_des, ingrediente=ingrediente)
            return float(round(convertida, 3)), (u_des.abreviatura or destino_txt), ''
        except ErrorConversionUnidad as exc:
            return float(round(val, 3)), origen_txt, str(exc)

    # Conversiones métricas directas cuando alguna unidad aún no está en tabla
    factores_directos = {
        ('g', 'kg'): Decimal('0.001'),
        ('kg', 'g'): Decimal('1000'),
        ('ml', 'l'): Decimal('0.001'),
        ('l', 'ml'): Decimal('1000'),
        ('g', 'lb'): Decimal('1') / Decimal('500'),
        ('lb', 'g'): Decimal('500'),
        ('kg', 'lb'): Decimal('2'),
        ('lb', 'kg'): Decimal('0.5'),
    }
    factor = factores_directos.get((origen_txt.lower(), destino_txt.lower()))
    if factor is not None:
        return float(round(val * factor, 3)), destino_txt, ''

    return float(round(val, 3)), origen_txt, f"Sin equivalencia configurada entre {origen_txt} y {destino_txt}"


def aplicar_conversiones_y_formulas_filas(
    tabla_def: dict,
    filas: list[dict],
    ingredientes_by_id: dict | None = None,
) -> tuple[list[dict], dict, list[str]]:
    """
    Aplica conversiones de unidad declaradas en columnas/tabla y evalúa fórmulas de fila y totales.
    """
    ingredientes_by_id = ingredientes_by_id or {}
    columnas = tabla_def.get('columnas') or []
    formulas_tabla = tabla_def.get('formulas') or []
    conversiones_tabla = tabla_def.get('conversiones_unidad') or []
    advertencias = []
    filas_procesadas = []

    for fila in filas:
        nueva = dict(fila)
        ing_obj = ingredientes_by_id.get(nueva.get('id_ingrediente'))
        unidad_actual = nueva.get('unidad') or nueva.get('unidad_medida') or ''

        # Conversiones definidas por columna
        for col in columnas:
            cod = col.get('codigo')
            unidad_dest = (col.get('unidad_destino') or '').strip()
            if cod and unidad_dest and cod in nueva and nueva[cod] not in (None, '', 'PENDIENTE'):
                val_conv, u_final, nota = convertir_valor_unidad_sirae(
                    nueva[cod],
                    str(nueva.get(f'{cod}_unidad') or unidad_actual),
                    unidad_dest,
                    ingrediente=ing_obj,
                )
                nueva[cod] = val_conv
                nueva[f'{cod}_unidad'] = u_final
                if nota and nota not in advertencias:
                    advertencias.append(nota)

        # Conversiones explícitas en la lista conversiones_unidad
        for conv in conversiones_tabla:
            if not conv.get('aplicar_automaticamente', True):
                continue
            col_ori = conv.get('columna_origen')
            col_des = conv.get('columna_destino') or col_ori
            u_ori = (conv.get('unidad_origen_abrev') or unidad_actual or '').strip()
            u_des = (conv.get('unidad_destino_abrev') or '').strip()
            if col_ori and col_des and u_des and col_ori in nueva and nueva[col_ori] not in (None, '', 'PENDIENTE'):
                val_conv, u_final, nota = convertir_valor_unidad_sirae(
                    nueva[col_ori],
                    u_ori,
                    u_des,
                    ingrediente=ing_obj,
                )
                nueva[col_des] = val_conv
                nueva[f'{col_des}_unidad'] = u_final
                if nota and nota not in advertencias:
                    advertencias.append(nota)

        # Fórmulas definidas en columnas
        for col in columnas:
            cod = col.get('codigo')
            expr = (col.get('formula') or '').strip()
            if cod and expr:
                nueva[cod] = evaluar_expresion_segura(expr, nueva)

        # Fórmulas adicionales de la tabla
        for frm in formulas_tabla:
            dest = frm.get('columna_destino')
            expr = (frm.get('expresion') or '').strip()
            if dest and expr:
                nueva[dest] = evaluar_expresion_segura(expr, nueva)
            elif dest and frm.get('operacion'):
                op = str(frm.get('operacion')).upper()
                a = _a_decimal(nueva.get(frm.get('campo_a')))
                b = _a_decimal(nueva.get(frm.get('campo_b')))
                if op == 'DIFF':
                    nueva[dest] = float(round(a - b, 3))
                elif op == 'MULT':
                    nueva[dest] = float(round(a * b, 3))
                elif op == 'DIV':
                    nueva[dest] = float(round(a / b, 3)) if b != 0 else 0.0
                elif op == 'PERCENT':
                    nueva[dest] = float(round((a / b) * Decimal('100'), 2)) if b != 0 else 0.0

        filas_procesadas.append(nueva)

    totales = {'total_registros': len(filas_procesadas)}
    for col in columnas:
        cod = col.get('codigo')
        if not cod:
            continue
        if col.get('calcular_total') or col.get('subtotal') or col.get('tipo') in {'NUMERO', 'MONEDA'}:
            valores = [
                _a_decimal(f.get(cod))
                for f in filas_procesadas
                if f.get(cod) not in (None, '', 'PENDIENTE')
            ]
            if valores or col.get('calcular_total'):
                totales[cod] = float(round(sum(valores, Decimal('0')), 3))

    return filas_procesadas, totales, advertencias


CODIGOS_PLANTILLAS_RETIRADAS_BASE = (
    'PAE-FMT-RECEPCION',
    'PAE-FMT-ASISTENCIA',
    'PAE-FMT-PREPARACION',
    'PAE-FMT-CONSUMO',
)


def construir_plantillas_oficiales_base() -> list[dict]:
    """
    Retorna únicamente las 2 plantillas oficiales reales del PAE proporcionadas en los formatos físicos
    (Remisión de Víveres e Insumos y Control de Entrada y Salida / Kárdex), enlazadas a fuentes reales de SIRAE.
    """
    return [
        {
            'codigo': 'PAE-FMT-REMISION',
            'nombre': 'Remisión de Víveres e Insumos por Comedor Escolar',
            'descripcion': 'Planilla del Supervisor para programar y controlar el despacho de víveres por sede asignada.',
            'categoria_proceso': 'REMISION',
            'finalidad': 'Documentar los alimentos programados y despachados hacia cada sede escolar según contrato y cupos.',
            'roles_autorizados': ['SuperAdministrador', 'supervisor'],
            'esquema': {
                'encabezado': {
                    'titulo': 'REMISIÓN DE VÍVERES E INSUMOS POR COMEDOR ESCOLAR',
                    'subtitulo': 'PROGRAMA DE ALIMENTACIÓN ESCOLAR - SIRAE',
                    'codigo_formato': 'PAE-FMT-REMISION',
                },
                'secciones': [
                    {'codigo': 'SEC_IDENTIFICACION', 'titulo': 'Datos de Institución, Sede y Contrato', 'orden': 1, 'origen': 'AUTOMATICO', 'fuente_sirae': 'CONTRATO'},
                    {'codigo': 'SEC_CUPOS', 'titulo': 'Cupos por Nivel Educativo y Grados', 'orden': 2, 'origen': 'AUTOMATICO', 'fuente_sirae': 'CUPOS_GRADOS'},
                    {'codigo': 'SEC_PRODUCTOS', 'titulo': 'Detalle de Alimentos Programados y Despachados', 'orden': 3, 'origen': 'AUTOMATICO', 'fuente_sirae': 'ABASTECIMIENTO_CALCULO'},
                    {'codigo': 'SEC_OBSERVACIONES', 'titulo': 'Observaciones y Firmas de Responsables', 'orden': 4, 'origen': 'MANUAL', 'fuente_sirae': 'FIRMAS_USUARIOS'},
                ],
                'campos': [
                    {'codigo': 'institucion_nombre', 'etiqueta': 'Institución educativa', 'seccion': 'SEC_IDENTIFICACION', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'INSTITUCION', 'campo_fuente': 'nombre_institucion', 'requerido': True},
                    {'codigo': 'sede_nombre', 'etiqueta': 'Sede escolar', 'seccion': 'SEC_IDENTIFICACION', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'SEDE', 'campo_fuente': 'nombre_sede', 'requerido': True},
                    {'codigo': 'codigo_dane', 'etiqueta': 'Código DANE sede', 'seccion': 'SEC_IDENTIFICACION', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'SEDE', 'campo_fuente': 'codigo_dane', 'requerido': False},
                    {'codigo': 'contrato_numero', 'etiqueta': 'Contrato PAE Nº', 'seccion': 'SEC_IDENTIFICACION', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'CONTRATO', 'campo_fuente': 'numero_cor', 'requerido': True},
                    {'codigo': 'operador_nombre', 'etiqueta': 'Operador / Contratista', 'seccion': 'SEC_IDENTIFICACION', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'CONTRATO', 'campo_fuente': 'operador', 'requerido': True},
                    {'codigo': 'total_cupos', 'etiqueta': 'Total cupos atendidos', 'seccion': 'SEC_CUPOS', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'CUPOS_GRADOS', 'campo_fuente': 'total_cupos', 'requerido': True},
                    {'codigo': 'observaciones_despacho', 'etiqueta': 'Observaciones adicionales de despacho', 'seccion': 'SEC_OBSERVACIONES', 'tipo': 'TEXTO', 'origen': 'MANUAL', 'fuente_sirae': '', 'campo_fuente': '', 'requerido': False},
                ],
                'tablas': [
                    {
                        'codigo': 'TABLA_REMISION_PRODUCTOS',
                        'titulo': 'Balance de Abastecimiento y Despacho por Producto',
                        'seccion': 'SEC_PRODUCTOS',
                        'fuente_sirae': 'CONSUMO',
                        'columnas': [
                            {'codigo': 'nombre_ingrediente', 'etiqueta': 'Producto / Ingrediente', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'ABASTECIMIENTO_CALCULO', 'campo_fuente': 'nombre_ingrediente'},
                            {'codigo': 'tipo_conservacion', 'etiqueta': 'Clasificación', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'ABASTECIMIENTO_CALCULO', 'campo_fuente': 'tipo_conservacion'},
                            {'codigo': 'unidad', 'etiqueta': 'Unidad', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'ABASTECIMIENTO_CALCULO', 'campo_fuente': 'unidad'},
                            {'codigo': 'cantidad_programada', 'etiqueta': 'Cant. Programada', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'ABASTECIMIENTO_CALCULO', 'campo_fuente': 'cantidad_programada', 'calcular_total': True},
                            {'codigo': 'cantidad_despachada', 'etiqueta': 'Cant. Despachada', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'ENTREGAS', 'campo_fuente': 'cantidad_despachada', 'calcular_total': True},
                            {'codigo': 'cantidad_recibida', 'etiqueta': 'Cant. Recibida', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'RECEPCIONES', 'campo_fuente': 'cantidad_recibida', 'calcular_total': True},
                            {'codigo': 'diferencia_despacho', 'etiqueta': 'Diferencia Despacho vs Programado', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'formula': 'cantidad_despachada - cantidad_programada', 'calcular_total': True},
                            {'codigo': 'estado_fila', 'etiqueta': 'Estado Registro', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'campo_fuente': 'estado_fila'},
                        ],
                        'formulas': [
                            {'codigo': 'DIF_REMISION', 'etiqueta': 'Diferencia despacho vs programado', 'operacion': 'DIFF', 'campo_a': 'cantidad_despachada', 'campo_b': 'cantidad_programada', 'columna_destino': 'diferencia_despacho'}
                        ],
                        'conversiones_unidad': [],
                    }
                ],
            },
        },
        {
            'codigo': 'PAE-FMT-INVENTARIO',
            'nombre': 'Control de Entrada y Salida de Alimentos',
            'descripcion': 'Planilla mensual de entradas, salidas de cocina y saldo del mes (diligenciada en comedor y verificada por Supervisor de campo).',
            'categoria_proceso': 'INVENTARIO',
            'finalidad': 'Registrar las entradas, salidas diarias y saldo mensual de alimentos en la sede escolar.',
            'roles_autorizados': ['SuperAdministrador', 'supervisor', 'Administrador', 'JefaManipuladoras', 'Manipuladora'],
            'esquema': {
                'encabezado': {
                    'titulo': 'CONTROL DE ENTRADA Y SALIDA DE ALIMENTOS',
                    'subtitulo': 'PROGRAMA DE ALIMENTACIÓN ESCOLAR PAE - SIRAE',
                    'codigo_formato': 'PAE-FMT-INVENTARIO',
                },
                'secciones': [
                    {'codigo': 'SEC_SALDOS', 'titulo': 'Saldos Actuales en Bodega Escolar', 'orden': 1, 'origen': 'AUTOMATICO', 'fuente_sirae': 'INVENTARIO'},
                    {'codigo': 'SEC_MOVIMIENTOS', 'titulo': 'Movimientos Kárdex (Entradas y Salidas)', 'orden': 2, 'origen': 'AUTOMATICO', 'fuente_sirae': 'KARDEX'},
                ],
                'campos': [
                    {'codigo': 'institucion_nombre', 'etiqueta': 'Institución educativa', 'seccion': 'SEC_SALDOS', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'INSTITUCION', 'campo_fuente': 'nombre_institucion', 'requerido': True},
                    {'codigo': 'sede_nombre', 'etiqueta': 'Sede educativa', 'seccion': 'SEC_SALDOS', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'fuente_sirae': 'SEDE', 'campo_fuente': 'nombre_sede', 'requerido': True},
                    {'codigo': 'verificacion_fisica', 'etiqueta': 'Verificación en comedor / supervisor de campo', 'seccion': 'SEC_SALDOS', 'tipo': 'TEXTO', 'origen': 'MANUAL', 'fuente_sirae': '', 'campo_fuente': '', 'requerido': False},
                ],
                'tablas': [
                    {
                        'codigo': 'TABLA_INVENTARIO_SALDOS',
                        'titulo': 'Control de Entradas, Salidas y Saldo del Mes',
                        'seccion': 'SEC_SALDOS',
                        'fuente_sirae': 'INVENTARIO',
                        'columnas': [
                            {'codigo': 'nombre_ingrediente', 'etiqueta': 'Alimento', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'campo_fuente': 'nombre_ingrediente'},
                            {'codigo': 'categoria', 'etiqueta': 'Categoría', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'campo_fuente': 'categoria'},
                            {'codigo': 'unidad', 'etiqueta': 'Unidad de medida', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'campo_fuente': 'unidad'},
                            {'codigo': 'total_entradas', 'etiqueta': 'Entrada', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'campo_fuente': 'total_entradas', 'calcular_total': True},
                            {'codigo': 'total_salidas', 'etiqueta': 'Total Salidas', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'campo_fuente': 'total_salidas', 'calcular_total': True},
                            {'codigo': 'cantidad_actual', 'etiqueta': 'Saldo del Mes', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'campo_fuente': 'cantidad_actual', 'calcular_total': True},
                            {'codigo': 'stock_minimo', 'etiqueta': 'Stock Mínimo', 'tipo': 'NUMERO', 'origen': 'AUTOMATICO', 'campo_fuente': 'stock_minimo', 'calcular_total': True},
                            {'codigo': 'estado_stock', 'etiqueta': 'Estado Stock', 'tipo': 'TEXTO', 'origen': 'AUTOMATICO', 'campo_fuente': 'estado_stock'},
                        ],
                        'formulas': [],
                        'conversiones_unidad': [],
                    }
                ],
            },
        },
    ]


def roles_por_plantilla_base_map() -> dict[str, list[str]]:
    """Mapa canonico codigo -> roles_autorizados para las plantillas base oficiales."""
    return {
        tpl['codigo']: normalizar_roles_lista(tpl.get('roles_autorizados'))
        for tpl in construir_plantillas_oficiales_base()
    }

