from copy import deepcopy
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps_sirae.reportes.models import PlantillaOficial, PlantillaVersion
from apps_sirae.reportes.services.catalogo_fuentes import (
    FUENTES_SIRAE,
    PROCESOS_PAE,
    ROLES_PLANTILLA_CANONICOS,
    construir_plantillas_oficiales_base,
    normalizar_roles_lista,
    usuario_autorizado_para_plantilla,
)


def validar_esquema_plantilla(esquema: dict) -> dict:
    if not isinstance(esquema, dict):
        raise ValidationError("El esquema de la plantilla debe ser un objeto JSON válido.")
    encabezado = esquema.get('encabezado') if isinstance(esquema.get('encabezado'), dict) else {}
    secciones = esquema.get('secciones') if isinstance(esquema.get('secciones'), list) else []
    campos = esquema.get('campos') if isinstance(esquema.get('campos'), list) else []
    tablas = esquema.get('tablas') if isinstance(esquema.get('tablas'), list) else []

    if not secciones and not campos and not tablas:
        raise ValidationError("La plantilla debe tener al menos una sección, campo o tabla configurada.")

    secciones_norm = []
    for idx, sec in enumerate(secciones, start=1):
        if not isinstance(sec, dict):
            continue
        codigo = (sec.get('codigo') or f'SEC_{idx}').strip()
        titulo = (sec.get('titulo') or f'Sección {idx}').strip()
        secciones_norm.append({
            'codigo': codigo,
            'titulo': titulo,
            'orden': int(sec.get('orden') or idx),
            'descripcion': (sec.get('descripcion') or '').strip(),
            'origen': (sec.get('origen') or 'AUTOMATICO').upper(),
            'fuente_sirae': (sec.get('fuente_sirae') or '').strip(),
            'visible_en_impresion': bool(sec.get('visible_en_impresion', True)),
        })

    campos_norm = []
    for idx, cmp_def in enumerate(campos, start=1):
        if not isinstance(cmp_def, dict):
            continue
        codigo = (cmp_def.get('codigo') or f'campo_{idx}').strip()
        etiqueta = (cmp_def.get('etiqueta') or codigo).strip()
        origen = (cmp_def.get('origen') or 'AUTOMATICO').upper()
        campos_norm.append({
            'codigo': codigo,
            'etiqueta': etiqueta,
            'seccion': (cmp_def.get('seccion') or (secciones_norm[0]['codigo'] if secciones_norm else 'GENERAL')).strip(),
            'tipo': (cmp_def.get('tipo') or 'TEXTO').upper(),
            'origen': origen if origen in {'AUTOMATICO', 'MANUAL'} else 'AUTOMATICO',
            'fuente_sirae': (cmp_def.get('fuente_sirae') or '').strip(),
            'campo_fuente': (cmp_def.get('campo_fuente') or '').strip(),
            'requerido': bool(cmp_def.get('requerido', False)),
            'formula': (cmp_def.get('formula') or '').strip(),
            'unidad_destino': (cmp_def.get('unidad_destino') or '').strip(),
        })

    tablas_norm = []
    for idx, tbl in enumerate(tablas, start=1):
        if not isinstance(tbl, dict):
            continue
        cols_in = tbl.get('columnas') if isinstance(tbl.get('columnas'), list) else []
        cols_norm = []
        for c_idx, col in enumerate(cols_in, start=1):
            if not isinstance(col, dict):
                continue
            c_cod = (col.get('codigo') or f'col_{c_idx}').strip()
            cols_norm.append({
                'codigo': c_cod,
                'etiqueta': (col.get('etiqueta') or c_cod).strip(),
                'tipo': (col.get('tipo') or 'TEXTO').upper(),
                'origen': (col.get('origen') or 'AUTOMATICO').upper(),
                'fuente_sirae': (col.get('fuente_sirae') or tbl.get('fuente_sirae') or '').strip(),
                'campo_fuente': (col.get('campo_fuente') or c_cod).strip(),
                'formula': (col.get('formula') or '').strip(),
                'unidad_destino': (col.get('unidad_destino') or '').strip(),
                'calcular_total': bool(col.get('calcular_total', False)),
                'subtotal': bool(col.get('subtotal', False)),
            })
        tablas_norm.append({
            'codigo': (tbl.get('codigo') or f'TABLA_{idx}').strip(),
            'titulo': (tbl.get('titulo') or f'Tabla {idx}').strip(),
            'seccion': (tbl.get('seccion') or (secciones_norm[0]['codigo'] if secciones_norm else 'GENERAL')).strip(),
            'fuente_sirae': (tbl.get('fuente_sirae') or 'CONSUMO').strip(),
            'columnas': cols_norm,
            'formulas': tbl.get('formulas') if isinstance(tbl.get('formulas'), list) else [],
            'conversiones_unidad': tbl.get('conversiones_unidad') if isinstance(tbl.get('conversiones_unidad'), list) else [],
        })

    return {
        'encabezado': {
            'titulo': (encabezado.get('titulo') or '').strip(),
            'subtitulo': (encabezado.get('subtitulo') or 'PROGRAMA DE ALIMENTACIÓN ESCOLAR - SIRAE').strip(),
            'codigo_formato': (encabezado.get('codigo_formato') or '').strip(),
        },
        'secciones': sorted(secciones_norm, key=lambda x: x['orden']),
        'campos': campos_norm,
        'tablas': tablas_norm,
    }


def asegurar_plantillas_oficiales_base(usuario=None):
    """
    Crea de forma idempotente el catálogo estructural inicial de plantillas oficiales PAE
    (sin datos operativos ficticios) cuando la tabla está vacía.
    """
    if PlantillaOficial.objects.exists():
        return
    with transaction.atomic():
        if PlantillaOficial.objects.exists():
            return
        ahora = timezone.now()
        for tpl in construir_plantillas_oficiales_base():
            plantilla = PlantillaOficial.objects.create(
                codigo=tpl['codigo'],
                nombre=tpl['nombre'],
                descripcion=tpl['descripcion'],
                categoria_proceso=tpl['categoria_proceso'],
                finalidad=tpl['finalidad'],
                roles_autorizados=normalizar_roles_lista(tpl['roles_autorizados']),
                activa=True,
                creado_por=usuario,
            )
            PlantillaVersion.objects.create(
                id_plantilla=plantilla,
                numero_version=1,
                estado='PUBLICADA',
                esquema=tpl['esquema'],
                notas_version='Versión estructural oficial inicial vinculada a fuentes SIRAE.',
                creado_por=usuario,
                publicado_por=usuario,
                fecha_publicacion=ahora,
            )


def crear_plantilla_con_borrador(data: dict, usuario) -> tuple[PlantillaOficial, PlantillaVersion]:
    codigo = (data.get('codigo') or '').strip().upper()
    nombre = (data.get('nombre') or '').strip()
    if not codigo:
        raise ValidationError("El código único de la plantilla es obligatorio.")
    if not nombre:
        raise ValidationError("El nombre de la plantilla es obligatorio.")
    if PlantillaOficial.objects.filter(codigo__iexact=codigo).exists():
        raise ValidationError(f"Ya existe una plantilla con el código '{codigo}'.")

    esquema_in = data.get('esquema')
    if not esquema_in:
        esquema_in = {
            'encabezado': {'titulo': nombre.upper(), 'codigo_formato': codigo},
            'secciones': [{'codigo': 'SEC_1', 'titulo': 'Sección Principal', 'orden': 1, 'origen': 'AUTOMATICO', 'fuente_sirae': 'CONTRATO'}],
            'campos': [],
            'tablas': [],
        }
    esquema_validado = validar_esquema_plantilla(esquema_in)

    with transaction.atomic():
        plantilla = PlantillaOficial.objects.create(
            codigo=codigo,
            nombre=nombre,
            descripcion=(data.get('descripcion') or '').strip(),
            categoria_proceso=(data.get('categoria_proceso') or 'OTRO').strip().upper(),
            finalidad=(data.get('finalidad') or '').strip(),
            roles_autorizados=normalizar_roles_lista(data.get('roles_autorizados')),
            activa=bool(data.get('activa', True)),
            creado_por=usuario,
        )
        version = PlantillaVersion.objects.create(
            id_plantilla=plantilla,
            numero_version=1,
            estado='BORRADOR',
            esquema=esquema_validado,
            notas_version=(data.get('notas_version') or 'Borrador inicial').strip(),
            creado_por=usuario,
        )
    return plantilla, version


def obtener_version_editable(plantilla: PlantillaOficial, id_version=None) -> PlantillaVersion:
    if id_version:
        version = PlantillaVersion.objects.filter(id_plantilla=plantilla, id_version=id_version).first()
    else:
        version = PlantillaVersion.objects.filter(id_plantilla=plantilla).order_by('-numero_version').first()
    if not version:
        raise ValidationError("La plantilla no tiene ninguna versión registrada.")
    if version.es_inmutable():
        raise ValidationError(
            f"La versión v{version.numero_version} ({version.estado}) es inmutable porque ya fue publicada o utilizada en documentos históricos. "
            "Cree una nueva versión en borrador para realizar cambios."
        )
    return version


def actualizar_plantilla_y_borrador(plantilla: PlantillaOficial, data: dict, usuario) -> tuple[PlantillaOficial, PlantillaVersion]:
    tiene_planillas_historicas = plantilla.versiones.filter(planillas_generadas__isnull=False).exists()
    edita_estructura = any(k in data for k in ('esquema', 'categoria_proceso', 'id_version'))

    with transaction.atomic():
        version_id = data.get('id_version')
        if edita_estructura:
            version = obtener_version_editable(plantilla, id_version=version_id)
            if 'esquema' in data:
                version.esquema = validar_esquema_plantilla(data['esquema'])
            if 'notas_version' in data:
                version.notas_version = (data.get('notas_version') or '').strip()
            version.save()
        else:
            version = PlantillaVersion.objects.filter(id_plantilla=plantilla).order_by('-numero_version').first()

        if 'categoria_proceso' in data:
            nueva_cat = (data['categoria_proceso'] or '').strip().upper()
            if tiene_planillas_historicas and nueva_cat != plantilla.categoria_proceso:
                raise ValidationError(
                    "No puede cambiar el proceso de una plantilla que ya cuenta con documentos históricos generados."
                )
            plantilla.categoria_proceso = nueva_cat
        if 'nombre' in data and (data.get('nombre') or '').strip():
            if version and version.es_inmutable() and not tiene_planillas_historicas:
                pass
            plantilla.nombre = data['nombre'].strip()
        if 'descripcion' in data:
            plantilla.descripcion = (data.get('descripcion') or '').strip()
        if 'finalidad' in data:
            plantilla.finalidad = (data.get('finalidad') or '').strip()
        if 'roles_autorizados' in data:
            plantilla.roles_autorizados = normalizar_roles_lista(data['roles_autorizados'])
        if 'activa' in data:
            plantilla.activa = bool(data['activa'])
        plantilla.save()

    return plantilla, version


def publicar_version(version: PlantillaVersion, usuario, notas: str = '') -> PlantillaVersion:
    if version.estado == 'ARCHIVADA':
        raise ValidationError("No se puede republicar una versión archivada directamente; genere una nueva versión.")
    if version.estado == 'PUBLICADA':
        return version

    validar_esquema_plantilla(version.esquema)
    with transaction.atomic():
        PlantillaVersion.objects.filter(
            id_plantilla=version.id_plantilla, estado='PUBLICADA'
        ).exclude(id_version=version.id_version).update(estado='ARCHIVADA')

        version.estado = 'PUBLICADA'
        version.publicado_por = usuario
        version.fecha_publicacion = timezone.now()
        if notas:
            version.notas_version = notas.strip()
        version.save()

        plantilla = version.id_plantilla
        if not plantilla.activa:
            plantilla.activa = True
            plantilla.save(update_fields=['activa', 'fecha_actualizacion'])

    return version


def crear_nueva_version(plantilla: PlantillaOficial, usuario, base_version: PlantillaVersion | None = None, notas: str = '') -> PlantillaVersion:
    if base_version is None:
        base_version = (
            plantilla.versiones.filter(estado='PUBLICADA').first()
            or plantilla.versiones.order_by('-numero_version').first()
        )
    if not base_version:
        raise ValidationError("No existe una versión base para clonar.")

    max_num = plantilla.versiones.aggregate(m=Max('numero_version')).get('m') or 0
    return PlantillaVersion.objects.create(
        id_plantilla=plantilla,
        numero_version=int(max_num) + 1,
        estado='BORRADOR',
        esquema=deepcopy(base_version.esquema),
        notas_version=(notas or f'Nueva versión basada en v{base_version.numero_version}').strip(),
        creado_por=usuario,
    )


def obtener_version_publicada_para_proceso(
    usuario,
    *,
    id_plantilla=None,
    categoria_proceso: str = '',
) -> PlantillaVersion:
    asegurar_plantillas_oficiales_base(usuario=usuario)

    if id_plantilla:
        plantilla = PlantillaOficial.objects.filter(id_plantilla=id_plantilla, activa=True).first()
    elif categoria_proceso:
        candidatas = list(
            PlantillaOficial.objects.filter(
                categoria_proceso=categoria_proceso.strip().upper(),
                activa=True,
            )
            .prefetch_related('versiones')
            .order_by('id_plantilla')
        )
        autorizadas = [p for p in candidatas if usuario_autorizado_para_plantilla(usuario, p)]
        plantilla = next(
            (p for p in autorizadas if p.versiones.filter(estado='PUBLICADA').exists()),
            autorizadas[0] if autorizadas else (candidatas[0] if candidatas else None),
        )
    else:
        raise ValidationError("Debe indicar una plantilla oficial o un proceso del PAE.")

    if not plantilla:
        raise ValidationError("No existe una plantilla oficial activa para el proceso seleccionado.")

    if not usuario_autorizado_para_plantilla(usuario, plantilla):
        raise ValidationError(
            f"Su rol no está autorizado para utilizar la plantilla '{plantilla.nombre}'."
        )

    version = plantilla.versiones.filter(estado='PUBLICADA').order_by('-numero_version').first()
    if not version:
        raise ValidationError(
            f"La plantilla '{plantilla.nombre}' aún no tiene una versión PUBLICADA. "
            "El Superadministrador debe publicarla primero."
        )
    return version


def obtener_catalogo_metadatos() -> dict:
    return {
        'procesos_pae': PROCESOS_PAE,
        'roles_disponibles': ROLES_PLANTILLA_CANONICOS,
        'fuentes_sirae': FUENTES_SIRAE,
    }

