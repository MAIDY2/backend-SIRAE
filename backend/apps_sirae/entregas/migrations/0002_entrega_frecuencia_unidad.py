from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('entregas', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='entrega',
            name='frecuencia',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='entrega',
            name='unidad',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
    ]
