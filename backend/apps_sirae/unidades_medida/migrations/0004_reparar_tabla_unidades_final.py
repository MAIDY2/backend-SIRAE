from django.db import migrations


def reparar_unidades_medida(apps, schema_editor):
    UnidadMedida = apps.get_model('unidades_medida', 'UnidadMedida')
    connection = schema_editor.connection

    tablas = connection.introspection.table_names()

    if 'unidades_medida' not in tablas:
        schema_editor.create_model(UnidadMedida)
        return

    with connection.cursor() as cursor:
        columnas = {
            columna.name
            for columna in connection.introspection.get_table_description(
                cursor,
                'unidades_medida'
            )
        }

    if 'nombre' in columnas and 'nombre_unidad' not in columnas:
        cursor_sql = connection.cursor()
        cursor_sql.execute(
            'ALTER TABLE unidades_medida RENAME COLUMN nombre TO nombre_unidad'
        )
        cursor_sql.close()
        columnas.remove('nombre')
        columnas.add('nombre_unidad')

    if 'descripcion' in columnas:
        cursor_sql = connection.cursor()
        cursor_sql.execute(
            'ALTER TABLE unidades_medida DROP COLUMN descripcion'
        )
        cursor_sql.close()


class Migration(migrations.Migration):

    dependencies = [
        ('unidades_medida', '0003_reparar_tabla_unidades'),
    ]

    operations = [
        migrations.RunPython(
            reparar_unidades_medida,
            migrations.RunPython.noop,
        ),
    ]
