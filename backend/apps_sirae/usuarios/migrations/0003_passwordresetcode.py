from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0002_usuario_groups_usuario_user_permissions_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PasswordResetCode",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("codigo_hash", models.CharField(max_length=128)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("expira_en", models.DateTimeField()),
                ("intentos_fallidos", models.PositiveSmallIntegerField(default=0)),
                (
                    "usuario",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="password_reset_code",
                        to="usuarios.usuario",
                    ),
                ),
            ],
            options={
                "db_table": "usuarios_codigo_recuperacion",
            },
        ),
    ]
