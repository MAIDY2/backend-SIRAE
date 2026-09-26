from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('contratos_pae', '0002_alter_contrato_estado_alter_contrato_id_contrato'),
        ('secciones_menu', '0003_alter_seccionmenu_options'),
    ]

    operations = [
        migrations.CreateModel(
            name='ContratoSeccionMenu',
            fields=[
                (
                    'id_contrato_seccion',
                    models.AutoField(
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    'valor',
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        max_digits=12,
                        null=True,
                    ),
                ),
                (
                    'condiciones',
                    models.TextField(
                        blank=True,
                        null=True,
                    ),
                ),
                (
                    'estado',
                    models.CharField(
                        blank=True,
                        max_length=30,
                        null=True,
                    ),
                ),
                (
                    'id_contrato',
                    models.ForeignKey(
                        db_column='id_contrato',
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to='contratos_pae.contrato',
                    ),
                ),
                (
                    'id_seccion',
                    models.ForeignKey(
                        db_column='id_seccion',
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        to='secciones_menu.seccionmenu',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Sección de contrato',
                'verbose_name_plural': 'Secciones de contrato',
                'db_table': 'contrato_seccion_menu',
                'managed': True,
            },
        ),
    ]