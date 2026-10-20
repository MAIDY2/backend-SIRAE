import django.db.models.deletion
from django.db import migrations, models


def crear_tabla_si_falta(apps, schema_editor):
    Gramage = apps.get_model("gramage", "Gramage")
    tablas = schema_editor.connection.introspection.table_names()

    if Gramage._meta.db_table not in tablas:
        schema_editor.create_model(Gramage)


class Migration(migrations.Migration):
    dependencies = [
        ("grados", "0003_reparar_tabla_grados"),
        ("gramage", "0002_alter_gramage_options"),
    ]

    operations = [
        migrations.RunPython(
            crear_tabla_si_falta,
            migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="gramage",
            name="id_grado",
            field=models.ForeignKey(
                db_column="id_grado",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="gramajes",
                to="grados.grados",
            ),
        ),
    ]
