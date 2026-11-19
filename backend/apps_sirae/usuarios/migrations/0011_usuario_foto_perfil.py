from django.db import migrations, models


def agregar_foto_perfil_seguro(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        tablas = connection.introspection.table_names(cursor)
        if "usuarios" not in tablas:
            return
        columnas = {
            col.name
            for col in connection.introspection.get_table_description(cursor, "usuarios")
        }
        if "foto_perfil" not in columnas:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN foto_perfil TEXT NULL"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0010_add_password_visible_to_usuario'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    agregar_foto_perfil_seguro,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='usuario',
                    name='foto_perfil',
                    field=models.TextField(
                        blank=True,
                        help_text='Imagen de perfil del usuario en formato base64 o URL.',
                        null=True,
                    ),
                ),
            ],
        ),
    ]
