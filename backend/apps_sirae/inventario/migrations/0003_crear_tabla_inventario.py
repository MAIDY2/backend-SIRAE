from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0002_alter_inventario_options'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[],
            database_operations=[
                migrations.CreateModel(
                    name='Inventario',
                    fields=[
                        (
                            'id_inventario',
                            models.AutoField(
                                primary_key=True,
                                serialize=False
                            ),
                        ),
                        (
                            'id_ingrediente',
                            models.IntegerField()
                        ),
                        (
                            'cantidad_actual',
                            models.DecimalField(
                                max_digits=10,
                                decimal_places=2
                            ),
                        ),
                        (
                            'stock_minimo',
                            models.DecimalField(
                                max_digits=10,
                                decimal_places=2
                            ),
                        ),
                        (
                            'id_unidad_medida',
                            models.IntegerField()
                        ),
                    ],
                    options={
                        'db_table': 'inventario',
                    },
                ),
            ],
        ),
    ]
