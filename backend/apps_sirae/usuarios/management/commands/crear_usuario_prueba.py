from django.core.management.base import BaseCommand
from apps_sirae.usuarios.models import Usuario


class Command(BaseCommand):

    def handle(self, *args, **kwargs):

        correo = "jhon.prueba@gmail.com"
        password = "JhonPrueba123"

        usuario, creado = Usuario.objects.get_or_create(
            correo=correo,
            defaults={
                "nombre": "Jhon",
                "apellido": "Prueba",
                "tipo_documento": "CC",
                "numero_documento": "88888888",
            },
        )

        usuario.set_password(password)
        usuario.is_active = True
        usuario.save()

        if creado:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Usuario creado: {usuario.correo}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Usuario actualizado: {usuario.correo}"
                )
            )
