from decimal import Decimal
from typing import Optional

from apps_sirae.unidades_medida.models import EquivalenciaUnidad, UnidadMedida


class ErrorConversionUnidad(Exception):
    """Error lanzado cuando se intenta convertir entre unidades incompatibles sin equivalencia técnica."""


_CATALOGO_DEFECTO = {
    'g': ('MASA', Decimal('1')),
    'gr': ('MASA', Decimal('1')),
    'gramo': ('MASA', Decimal('1')),
    'gramos': ('MASA', Decimal('1')),
    'kg': ('MASA', Decimal('1000')),
    'kilo': ('MASA', Decimal('1000')),
    'kilogramo': ('MASA', Decimal('1000')),
    'kilogramos': ('MASA', Decimal('1000')),
    'lb': ('MASA', Decimal('500')),
    'libra': ('MASA', Decimal('500')),
    'libras': ('MASA', Decimal('500')),
    'oz': ('MASA', Decimal('28.3495')),
    'onza': ('MASA', Decimal('28.3495')),
    'onzas': ('MASA', Decimal('28.3495')),
    'mg': ('MASA', Decimal('0.001')),
    'ml': ('VOLUMEN', Decimal('1')),
    'mililitro': ('VOLUMEN', Decimal('1')),
    'mililitros': ('VOLUMEN', Decimal('1')),
    'cc': ('VOLUMEN', Decimal('1')),
    'l': ('VOLUMEN', Decimal('1000')),
    'lt': ('VOLUMEN', Decimal('1000')),
    'litro': ('VOLUMEN', Decimal('1000')),
    'litros': ('VOLUMEN', Decimal('1000')),
    'und': ('UNIDAD', Decimal('1')),
    'unid': ('UNIDAD', Decimal('1')),
    'u': ('UNIDAD', Decimal('1')),
    'unidad': ('UNIDAD', Decimal('1')),
    'unidades': ('UNIDAD', Decimal('1')),
    'pza': ('UNIDAD', Decimal('1')),
    'pieza': ('UNIDAD', Decimal('1')),
    'paq': ('UNIDAD', Decimal('1')),
    'paquete': ('UNIDAD', Decimal('1')),
    'bolsa': ('UNIDAD', Decimal('1')),
    'docena': ('UNIDAD', Decimal('12')),
}


def inferir_info_unidad(unidad: UnidadMedida) -> tuple[str, Decimal]:
    """
    Obtiene (tipo_magnitud, factor_conversion_base) usando el valor configurado en BD
    y como respaldo deduce abreviaturas estándar si el registro fue creado antes de la migración.
    """
    abrev = (unidad.abreviatura or '').strip().lower()
    nombre = (unidad.nombre or '').strip().lower()

    magnitud = getattr(unidad, 'tipo_magnitud', None) or 'MASA'
    factor = Decimal(str(getattr(unidad, 'factor_conversion_base', None) or '1'))

    # Respaldo seguro para unidades heredadas sin parametrizar
    clave_match = abrev if abrev in _CATALOGO_DEFECTO else (nombre if nombre in _CATALOGO_DEFECTO else None)
    if clave_match and factor == Decimal('1') and magnitud == 'MASA':
        mag_inf, fac_inf = _CATALOGO_DEFECTO[clave_match]
        return mag_inf, fac_inf

    if factor <= 0:
        factor = Decimal('1')

    return magnitud, factor


def verificar_compatibilidad_unidades(
    unidad_origen: UnidadMedida,
    unidad_destino: UnidadMedida,
    ingrediente=None,
) -> tuple[bool, str, Optional[Decimal]]:
    """
    Verifica si es posible convertir desde `unidad_origen` hacia `unidad_destino`
    (directamente por misma magnitud o vía equivalencia técnica configurada para el producto).
    Retorna: (es_compatible, metodo, factor_calculado_directo)
      - metodo: 'IGUAL' | 'MISMA_MAGNITUD' | 'EQUIVALENCIA_TECNICA' | 'INCOMPATIBLE'
    """
    if unidad_origen.pk == unidad_destino.pk:
        return True, 'IGUAL', Decimal('1')

    mag_ori, fac_ori = inferir_info_unidad(unidad_origen)
    mag_des, fac_des = inferir_info_unidad(unidad_destino)

    if mag_ori == mag_des:
        if fac_des <= 0:
            return False, 'INCOMPATIBLE', None
        factor = fac_ori / fac_des
        return True, 'MISMA_MAGNITUD', factor

    # Magnitudes diferentes: REQUIERE equivalencia técnica configurada para el ingrediente
    if ingrediente is None:
        return False, 'INCOMPATIBLE', None

    ing_id = ingrediente.pk if hasattr(ingrediente, 'pk') else ingrediente
    equivalencias = EquivalenciaUnidad.objects.filter(
        id_ingrediente_id=ing_id,
        estado='ACTIVO'
    ).select_related('id_unidad_origen', 'id_unidad_destino')

    for eq in equivalencias:
        mag_eq_ori, fac_eq_ori = inferir_info_unidad(eq.id_unidad_origen)
        mag_eq_des, fac_eq_des = inferir_info_unidad(eq.id_unidad_destino)
        factor_eq = Decimal(str(eq.factor_conversion))
        if factor_eq <= 0:
            continue

        # Caso directo: magnitud origen -> magnitud destino de equivalencia
        if mag_ori == mag_eq_ori and mag_des == mag_eq_des:
            # 1) origen -> eq_origen
            ratio_a_eq_ori = fac_ori / fac_eq_ori
            # 2) eq_origen -> eq_destino (* factor_eq)
            # 3) eq_destino -> destino
            ratio_desde_eq_des = fac_eq_des / fac_des
            factor_total = ratio_a_eq_ori * factor_eq * ratio_desde_eq_des
            return True, 'EQUIVALENCIA_TECNICA', factor_total

        # Caso inverso: magnitud origen coincide con eq_destino y destino coincide con eq_origen
        if mag_ori == mag_eq_des and mag_des == mag_eq_ori:
            ratio_a_eq_des = fac_ori / fac_eq_des
            ratio_desde_eq_ori = fac_eq_ori / fac_des
            factor_total = ratio_a_eq_des * (Decimal('1') / factor_eq) * ratio_desde_eq_ori
            return True, 'EQUIVALENCIA_TECNICA', factor_total

    return False, 'INCOMPATIBLE', None


def convertir_cantidad(
    cantidad: Decimal | float | int | str,
    unidad_origen: UnidadMedida,
    unidad_destino: UnidadMedida,
    ingrediente=None,
) -> Decimal:
    """
    Convierte `cantidad` desde `unidad_origen` hacia `unidad_destino`.
    Lanza `ErrorConversionUnidad` si no son compatibles o falta equivalencia técnica.
    """
    cant_dec = Decimal(str(cantidad))
    es_ok, metodo, factor = verificar_compatibilidad_unidades(
        unidad_origen, unidad_destino, ingrediente=ingrediente
    )

    if not es_ok or factor is None:
        mag_o, _ = inferir_info_unidad(unidad_origen)
        mag_d, _ = inferir_info_unidad(unidad_destino)
        raise ErrorConversionUnidad(
            f"No existe una conversión válida de '{unidad_origen.nombre} ({mag_o})' "
            f"a '{unidad_destino.nombre} ({mag_d})' sin una equivalencia técnica configurada para este producto."
        )

    return (cant_dec * factor).quantize(Decimal('0.000001'))


def obtener_unidades_compatibles_producto(ingrediente) -> list[dict]:
    """
    Lista todas las unidades activas indicando cuáles son compatibles con la unidad base
    del ingrediente (por misma magnitud o mediante equivalencia técnica configurada).
    """
    unidad_base = getattr(ingrediente, 'id_unidad_medida', None)
    unidades = UnidadMedida.objects.filter(estado='ACTIVO').order_by('tipo_magnitud', 'nombre')

    resultado = []
    for u in unidades:
        mag, fac = inferir_info_unidad(u)
        if unidad_base is None:
            compatible, metodo, factor = True, 'SIN_UNIDAD_BASE', None
        else:
            compatible, metodo, factor = verificar_compatibilidad_unidades(u, unidad_base, ingrediente=ingrediente)

        resultado.append({
            'id_unidad_medida': u.id_unidad_medida,
            'nombre': u.nombre,
            'abreviatura': u.abreviatura,
            'tipo_magnitud': mag,
            'factor_conversion_base': float(fac),
            'es_compatible': compatible,
            'metodo_compatibilidad': metodo,
            'requiere_equivalencia': metodo == 'INCOMPATIBLE',
        })
    return resultado


def formatear_cantidad_apropiada(cantidad: Decimal | float, unidad: Optional[UnidadMedida]) -> dict:
    """
    Presenta el resultado en una unidad apropiada para consulta y operación
    (ej. 1500 g -> 1.5 kg; 0.05 kg -> 50 g; 1500 ml -> 1.5 L).
    """
    cant = Decimal(str(cantidad or 0))
    if unidad is None:
        return {
            'cantidad': float(round(cant, 3)),
            'unidad': '',
            'texto': str(round(cant, 3)),
        }

    mag, fac = inferir_info_unidad(unidad)
    abrev = unidad.abreviatura or unidad.nombre

    # Convertir a unidad apropiada dentro de su magnitud (solo si existen unidades estándar en catálogo)
    if mag == 'MASA':
        en_gramos = cant * fac
        if en_gramos >= Decimal('1000'):
            return {
                'cantidad': float(round(en_gramos / Decimal('1000'), 3)),
                'unidad': 'kg',
                'texto': f"{float(round(en_gramos / Decimal('1000'), 3))} kg",
            }
        return {
            'cantidad': float(round(en_gramos, 3)),
            'unidad': 'g',
            'texto': f"{float(round(en_gramos, 3))} g",
        }

    if mag == 'VOLUMEN':
        en_ml = cant * fac
        if en_ml >= Decimal('1000'):
            return {
                'cantidad': float(round(en_ml / Decimal('1000'), 3)),
                'unidad': 'L',
                'texto': f"{float(round(en_ml / Decimal('1000'), 3))} L",
            }
        return {
            'cantidad': float(round(en_ml, 3)),
            'unidad': 'ml',
            'texto': f"{float(round(en_ml, 3))} ml",
        }

    return {
        'cantidad': float(round(cant, 3)),
        'unidad': abrev,
        'texto': f"{float(round(cant, 3))} {abrev}",
    }

