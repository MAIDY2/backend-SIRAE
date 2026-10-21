from django.db import migrations


def create_default_market_types(apps, schema_editor):
    TipoMercado = apps.get_model('tipos_mercado', 'TipoMercado')
    database = schema_editor.connection.alias
    existing_names = [
        nombre.strip().casefold()
        for nombre in TipoMercado.objects.using(database).values_list('nombre_tipo', flat=True)
    ]

    defaults = (
        ('Granos', ('granos', 'no perecederos', 'no perecedero')),
        ('Perecederos', ('perecederos', 'perecedero')),
    )
    for nombre, aliases in defaults:
        if not any(
            existente.startswith(alias)
            for existente in existing_names
            for alias in aliases
        ):
            TipoMercado.objects.using(database).create(nombre_tipo=nombre)
            existing_names.append(nombre.casefold())


class Migration(migrations.Migration):

    dependencies = [
        ('tipos_mercado', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_default_market_types, migrations.RunPython.noop),
    ]
