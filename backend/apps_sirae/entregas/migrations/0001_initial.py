from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Entrega',
            fields=[
                ('id_entrega', models.AutoField(primary_key=True, serialize=False)),
                ('id_ingrediente', models.IntegerField()),
                ('id_usuario_supervisor', models.IntegerField()),
                ('id_tipo_mercado', models.IntegerField()),
                ('fecha_entrega', models.DateField()),
                ('fecha_vencimiento', models.DateField()),
                ('cantidad', models.DecimalField(decimal_places=2, max_digits=10)),
                ('observaciones', models.TextField(blank=True)),
            ],
            options={'db_table': 'entregas'},
        ),
    ]