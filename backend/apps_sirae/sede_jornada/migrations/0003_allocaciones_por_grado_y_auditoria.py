import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('grados', '0003_reparar_tabla_grados'),
        ('sede_jornada', '0002_sedejornada_cupos'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='HistorialConfiguracionSede',
            fields=[
                ('id_historial', models.AutoField(primary_key=True, serialize=False)),
                ('fecha_hora', models.DateTimeField(auto_now_add=True)),
                ('valores_anteriores', models.JSONField(default=dict)),
                ('valores_nuevos', models.JSONField(default=dict)),
                (
                    'id_sede',
                    models.ForeignKey(
                        db_column='id_sede',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='historial_configuracion',
                        to='sedes.sede',
                    ),
                ),
                (
                    'usuario',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='historial_configuracion_sedes',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'db_table': 'historial_configuracion_sede',
                'ordering': ('-fecha_hora', '-id_historial'),
            },
        ),
        migrations.CreateModel(
            name='SedeJornadaGrado',
            fields=[
                (
                    'id_sede_jornada_grado',
                    models.AutoField(primary_key=True, serialize=False),
                ),
                ('cupos', models.PositiveIntegerField(default=0)),
                (
                    'id_grado',
                    models.ForeignKey(
                        db_column='id_grado',
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='cupos_por_sede_jornada',
                        to='grados.grados',
                    ),
                ),
                (
                    'id_sede_jornada',
                    models.ForeignKey(
                        db_column='id_sede_jornada',
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='grados',
                        to='sede_jornada.sedejornada',
                    ),
                ),
            ],
            options={
                'db_table': 'sede_jornada_grado',
                'constraints': [
                    models.UniqueConstraint(
                        fields=('id_sede_jornada', 'id_grado'),
                        name='unique_grado_per_sede_jornada',
                    ),
                ],
            },
        ),
    ]
