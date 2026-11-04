from django.db import migrations


def create_table_if_missing(apps, schema_editor):
    from apps_sirae.entradas_inventario.models import EntradaInventario

    table_name = EntradaInventario._meta.db_table
    existing_tables = schema_editor.connection.introspection.table_names()
    if table_name not in existing_tables:
        schema_editor.create_model(EntradaInventario)


class Migration(migrations.Migration):

    dependencies = [
        ('entradas_inventario', '0001_initial'),
        ('ingredientes', '0004_ingrediente_id_tipo_mercado'),
        ('unidades_medida', '0006_alter_unidadmedida_options_and_more'),
        ('usuarios', '0005_usuario_id_institucion_usuario_id_sede'),
    ]

    operations = [
        migrations.RunPython(create_table_if_missing, migrations.RunPython.noop),
    ]
