from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import identify_hasher
from apps_sirae.usuarios.models import Usuario


class Command(BaseCommand):
    help = "Revisa todos los usuarios en la base de datos y hashea cualquier contraseña guardada en texto plano."

    def handle(self, *args, **options):
        usuarios = Usuario.objects.all()
        actualizados = 0
        total = 0

        self.stdout.write(self.style.NOTICE("Verificando contraseñas de los usuarios..."))

        for usuario in usuarios:
            total += 1
            if not usuario.password:
                continue

            es_plano = False
            try:
                identify_hasher(usuario.password)
            except ValueError:
                es_plano = True

            if es_plano:
                usuario.set_password(usuario.password)
                usuario.save(update_fields=['password'])
                actualizados += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Contraseña hasheada para usuario ID {usuario.id_usuario} ({usuario.correo})"
                    )
                )

        if actualizados > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n¡Éxito! Se hashearon {actualizados} contraseñas de un total de {total} usuarios."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nTodas las contraseñas ({total} usuarios) ya estaban hasheadas correctamente."
                )
            )

