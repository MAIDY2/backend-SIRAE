import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('notificaciones', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='notificacion',
            name='fecha_hora',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
    ]