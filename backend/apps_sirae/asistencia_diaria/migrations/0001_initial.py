from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='AsistenciaDiaria',
            fields=[
                ('id_asistencia', models.AutoField(primary_key=True, serialize=False)),
                ('id_grado', models.IntegerField()),
                ('fecha', models.DateField()),
                ('ninos_presentes', models.PositiveIntegerField()),
                ('id_usuario_manipuladora', models.IntegerField()),
            ],
            options={'db_table': 'asistencia_diaria'},
        ),
    ]