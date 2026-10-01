from django.core.management.base import BaseCommand
from apps_sirae.usuarios.models import Usuario
from apps_sirae.roles.models import Rol


class Command(BaseCommand):
    help = "Crea los usuarios de prueba con sus respectivos roles"

    def handle(self, *args, **kwargs):

        roles = [
            ("Administrador", "Acceso administrativo del sistema"),
            ("supervisor", "Supervisión de manipuladoras y procesos del PAE"),
            ("JefaManipuladoras", "Gestión de manipuladoras"),
            ("Manipuladora", "Gestión de procesos asignados"),
        ]

        for nombre, descripcion in roles:
            Rol.objects.get_or_create(
                nombre=nombre,
                defaults={"descripcion": descripcion}
            )

        usuarios = [
            (
                "admin@sirae.com",
                "Administrador",
                "Sistema",
                "Administrador",
                "RENDER001",
            ),
            (
                "supervisor@sirae.com",
                "Supervisor",
                "SIRAE",
                "supervisor",
                "RENDER002",
            ),
            (
                "jefe@sirae.com",
                "Jefa",
                "Manipuladoras",
                "JefaManipuladoras",
                "RENDER003",
            ),
            (
                "manipuladora@sirae.com",
                "Manipuladora",
                "PAE",
                "Manipuladora",
                "RENDER004",
            ),
        ]

        password = "Sirae12345"

        for correo, nombre, apellido, nombre_rol, documento in usuarios:

            rol = Rol.objects.get(nombre=nombre_rol)

            usuario, creado = Usuario.objects.get_or_create(
                correo=correo,
                defaults={
                    "nombre": nombre,
                    "apellido": apellido,
                    "tipo_documento": "CC",
                    "numero_documento": documento,
                },
            )

            usuario.nombre = nombre
            usuario.apellido = apellido
            usuario.rol = rol
            usuario.is_active = True
            usuario.set_password(password)
            usuario.save()

            accion = "creado" if creado else "actualizado"

            self.stdout.write(
                self.style.SUCCESS(
                    f"Usuario {accion}: {correo} - Rol: {nombre_rol}"
                )
            )
