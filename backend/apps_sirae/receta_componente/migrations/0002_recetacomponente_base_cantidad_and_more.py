from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('receta_componente', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='recetacomponente',
            name='base_cantidad',
            field=models.CharField(
                blank=True,
                choices=[
                    ('POR_NINO', 'Por niño'),
                    ('TOTAL_PREPARACION', 'Total para una preparación'),
                ],
                max_length=20,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='recetacomponente',
            name='porciones_base',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
