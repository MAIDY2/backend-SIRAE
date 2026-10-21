from django.db import migrations


def crear_tabla_si_falta(apps, schema_editor):
    Grados = apps.get_model("grados", "Grados")
    tablas = schema_editor.connection.introspection.table_names()

    if Grados._meta.db_table not in tablas:
        schema_editor.create_model(Grados)


class Migration(migrations.Migration):
    dependencies = [
        ("grados", "0002_alter_grados_options"),
    ]

    operations = [
        migrations.RunPython(
            crear_tabla_si_falta,
            migrations.RunPython.noop,
        ),
    ]
