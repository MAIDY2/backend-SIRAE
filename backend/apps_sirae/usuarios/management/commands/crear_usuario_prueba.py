from django.core.management.base import BaseCommand
from apps_sirae.usuarios.models import Usuario


class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        correo = "jhon.prueba@gmail.com"

        if Usuario.objects.filter(correo=correo).exists():
            self.stdout.write("El usuario de prueba ya existe.")
            return

        usuario = Usuario.objects.create_user(
            correo=correo,
            nombre="Jhon",
            apellido="Prueba",
            password="JhonPrueba123",
            tipo_documento="CC",
            numero_documento="88888888",
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Usuario creado: {usuario.correo}"
            )
        )
