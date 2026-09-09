from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='MovimientoInventario',
            fields=[
                ('id_movimiento_inventario', models.AutoField(primary_key=True, serialize=False)),
                ('id_ingrediente', models.IntegerField()),
                ('id_usuario_manipuladora', models.IntegerField()),
                ('tipo_movimiento', models.CharField(max_length=30)),
                ('fecha', models.DateTimeField()),
                ('cantidad', models.DecimalField(decimal_places=2, max_digits=10)),
                ('observaciones', models.TextField(blank=True)),
                ('id_unidad_medida', models.IntegerField()),
            ],
            options={'db_table': 'movimientos_inventario'},
        ),
    ]