from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('roles', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Usuario',
            fields=[
                (
                    'id_usuario',
                    models.AutoField(
                        primary_key=True,
                        serialize=False
                    )
                ),
                (
                    'nombre',
                    models.CharField(max_length=100)
                ),
                (
                    'apellido',
                    models.CharField(max_length=100)
                ),
                (
                    'correo',
                    models.EmailField(
                        max_length=150,
                        unique=True
                    )
                ),
                (
                    'tipo_documento',
                    models.CharField(max_length=20)
                ),
                (
                    'numero_documento',
                    models.CharField(
                        max_length=20,
                        unique=True
                    )
                ),
                (
                    'rol',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name='usuarios',
                        to='roles.rol'
                    )
                ),
                (
                    'password',
                    models.CharField(max_length=128)
                ),
                (
                    'last_login',
                    models.DateTimeField(
                        blank=True,
                        null=True
                    )
                ),
                (
                    'is_active',
                    models.BooleanField(default=True)
                ),
                (
                    'is_staff',
                    models.BooleanField(default=False)
                ),
                (
                    'is_superuser',
                    models.BooleanField(default=False)
                ),
            ],
            options={
                'db_table': 'usuarios',
            },
        ),
    ]