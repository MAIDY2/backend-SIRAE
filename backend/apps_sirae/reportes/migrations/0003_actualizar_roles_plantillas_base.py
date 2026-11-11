from django.db import migrations

from apps_sirae.reportes.services.catalogo_fuentes import (
    CODIGOS_PLANTILLAS_RETIRADAS_BASE,
    construir_plantillas_oficiales_base,
    roles_por_plantilla_base_map,
)


def actualizar_roles_plantillas_base(apps, schema_editor):
    """
    Mantiene únicamente las 2 plantillas oficiales reales de los formatos proporcionados
    (Remisión de Víveres y Control de Entrada y Salida / Kárdex) y retira las adicionales
    no solicitadas sin romper documentos históricos si existieran.
    """
    PlantillaOficial = apps.get_model('reportes', 'PlantillaOficial')
    PlanillaGenerada = apps.get_model('reportes', 'PlanillaGenerada')
    roles_map = roles_por_plantilla_base_map()

    for tpl in construir_plantillas_oficiales_base():
        codigo = tpl['codigo']
        plantilla = PlantillaOficial.objects.filter(codigo=codigo).first()
        if not plantilla:
            continue
        plantilla.roles_autorizados = roles_map[codigo]
        plantilla.nombre = tpl['nombre']
        plantilla.descripcion = tpl['descripcion']
        plantilla.finalidad = tpl['finalidad']
        plantilla.activa = True
        plantilla.save(update_fields=['roles_autorizados', 'nombre', 'descripcion', 'finalidad', 'activa'])

    for codigo_retirado in CODIGOS_PLANTILLAS_RETIRADAS_BASE:
        plantilla = PlantillaOficial.objects.filter(codigo=codigo_retirado).first()
        if not plantilla:
            continue
        tiene_historicas = PlanillaGenerada.objects.filter(
            id_plantilla_version__id_plantilla_id=plantilla.id_plantilla
        ).exists()
        if tiene_historicas:
            plantilla.activa = False
            plantilla.save(update_fields=['activa'])
        else:
            plantilla.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('reportes', '0002_plantillas_oficiales_base'),
    ]

    operations = [
        migrations.RunPython(actualizar_roles_plantillas_base, migrations.RunPython.noop),
    ]
