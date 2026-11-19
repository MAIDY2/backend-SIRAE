from django.db import migrations, models


def agregar_password_visible_seguro(apps, schema_editor):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        tablas = connection.introspection.table_names(cursor)
        if "usuarios" not in tablas:
            return
        columnas = {
            col.name
            for col in connection.introspection.get_table_description(cursor, "usuarios")
        }
        if "password_visible" not in columnas:
            cursor.execute(
                "ALTER TABLE usuarios ADD COLUMN password_visible VARCHAR(128) NOT NULL DEFAULT ''"
            )


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0009_usuario_id_jornada'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    agregar_password_visible_seguro,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='usuario',
                    name='password_visible',
                    field=models.CharField(
                        blank=True,
                        default='',
                        help_text='Contraseña inicial asignada por el administrador (solo uso interno). Se limpia automáticamente cuando el usuario cambia su clave por cuenta propia.',
                        max_length=128,
                    ),
                ),
            ],
        ),
    ]
