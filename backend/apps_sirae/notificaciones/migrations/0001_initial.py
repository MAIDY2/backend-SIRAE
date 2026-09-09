from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Notificacion',
            fields=[
                ('id_notificacion', models.AutoField(primary_key=True, serialize=False)),
                ('id_usuario', models.IntegerField()),
                ('titulo', models.CharField(max_length=150)),
                ('mensaje', models.TextField()),
                ('fecha_hora', models.DateTimeField()),
                ('leida', models.BooleanField(default=False)),
            ],
            options={'db_table': 'notificaciones'},
        ),
    ]