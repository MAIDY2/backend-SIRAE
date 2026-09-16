from django.db import migrations


def reparar_unidades_medida(apps, schema_editor):
    connection = schema_editor.connection
    vendor = connection.vendor

    with connection.cursor() as cursor:
        if vendor == 'postgresql':
            cursor.execute("""
                DO $$
                BEGIN
                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'unidades_medida'
                        AND column_name = 'nombre'
                    )
                    AND NOT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'unidades_medida'
                        AND column_name = 'nombre_unidad'
                    ) THEN
                        ALTER TABLE unidades_medida
                        RENAME COLUMN nombre TO nombre_unidad;
                    END IF;

                    IF EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'unidades_medida'
                        AND column_name = 'descripcion'
                    ) THEN
                        ALTER TABLE unidades_medida
                        DROP COLUMN descripcion;
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'unidades_medida'
                        AND column_name = 'nombre_unidad'
                    ) THEN
                        ALTER TABLE unidades_medida
                        ADD COLUMN nombre_unidad VARCHAR(50) NOT NULL DEFAULT 'Sin nombre';
                    END IF;

                    IF NOT EXISTS (
                        SELECT 1
                        FROM information_schema.columns
                        WHERE table_name = 'unidades_medida'
                        AND column_name = 'abreviatura'
                    ) THEN
                        ALTER TABLE unidades_medida
                        ADD COLUMN abreviatura VARCHAR(10) NULL;
                    END IF;
                END
                $$;
            """)


class Migration(migrations.Migration):

    dependencies = [
        ('unidades_medida', '0002_alter_unidadmedida_options_and_more'),
    ]

    operations = [
        migrations.RunPython(
            reparar_unidades_medida,
            migrations.RunPython.noop,
        ),
    ]
