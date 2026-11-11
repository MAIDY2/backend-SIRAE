from django.db import migrations
from django.utils import timezone

from apps_sirae.reportes.services.catalogo_fuentes import (
    construir_plantillas_oficiales_base,
    normalizar_roles_lista,
)


def crear_plantillas_oficiales_iniciales(apps, schema_editor):
    PlantillaOficial = apps.get_model('reportes', 'PlantillaOficial')
    PlantillaVersion = apps.get_model('reportes', 'PlantillaVersion')

    if PlantillaOficial.objects.exists():
        return

    ahora = timezone.now()
    for tpl in construir_plantillas_oficiales_base():
        plantilla, creada = PlantillaOficial.objects.get_or_create(
            codigo=tpl['codigo'],
            defaults={
                'nombre': tpl['nombre'],
                'descripcion': tpl['descripcion'],
                'categoria_proceso': tpl['categoria_proceso'],
                'finalidad': tpl['finalidad'],
                'roles_autorizados': normalizar_roles_lista(tpl['roles_autorizados']),
                'activa': True,
            },
        )
        if not PlantillaVersion.objects.filter(id_plantilla=plantilla).exists():
            PlantillaVersion.objects.create(
                id_plantilla=plantilla,
                numero_version=1,
                estado='PUBLICADA',
                esquema=tpl['esquema'],
                notas_version='Versión estructural oficial inicial vinculada a fuentes SIRAE.',
                fecha_publicacion=ahora,
            )


class Migration(migrations.Migration):

    dependencies = [
        ('reportes', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            crear_plantillas_oficiales_iniciales,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

