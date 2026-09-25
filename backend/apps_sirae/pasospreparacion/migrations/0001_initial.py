from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='pasospreparacion',
            fields=[
                ('id_plato', models.AutoField(primary_key=True, serialize=False)),
                ('numero_paso', models.CharField(max_length=100)),
                ('descripcion', models.CharField(max_length=100)),
            ],
        ),
    ]
