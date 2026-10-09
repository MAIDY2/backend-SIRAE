import getpass
import os

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps_sirae.roles.models import Rol
from apps_sirae.usuarios.models import Usuario


class Command(BaseCommand):
    help = "Crea las cuentas oficiales; no cambia claves existentes sin confirmación."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset-existing-passwords",
            action="store_true",
            help="Solicita y reemplaza también las claves de las cuentas ya existentes.",
        )
        parser.add_argument(
            "--non-interactive",
            action="store_true",
            help=(
                "Lee las contraseñas de SIRAE_ADMIN_PASSWORD, "
                "SIRAE_SUPERVISOR_PASSWORD, SIRAE_JEFE_PASSWORD y "
                "SIRAE_MANIPULADORA_PASSWORD."
            ),
        )

    def handle(self, *args, **options):
        roles = [
            ("Administrador", "Acceso administrativo del sistema"),
            ("supervisor", "Supervisión de manipuladoras y procesos del PAE"),
            ("JefaManipuladoras", "Gestión de manipuladoras"),
            ("Manipuladora", "Gestión de procesos asignados"),
        ]
        for nombre, descripcion in roles:
            Rol.objects.get_or_create(nombre=nombre, defaults={"descripcion": descripcion})

        cuentas = [
            ("admin@sirae.com", "Administrador", "Sistema", "Administrador", "RENDER001"),
            ("supervisor@sirae.com", "Supervisor", "SIRAE", "supervisor", "RENDER002"),
            ("jefe@sirae.com", "Jefa", "Manipuladoras", "JefaManipuladoras", "RENDER003"),
            ("manipuladora@sirae.com", "Manipuladora", "PAE", "Manipuladora", "RENDER004"),
        ]
        password_envs = {
            "admin@sirae.com": "SIRAE_ADMIN_PASSWORD",
            "supervisor@sirae.com": "SIRAE_SUPERVISOR_PASSWORD",
            "jefe@sirae.com": "SIRAE_JEFE_PASSWORD",
            "manipuladora@sirae.com": "SIRAE_MANIPULADORA_PASSWORD",
        }

        passwords = {}
        for correo, nombre, apellido, nombre_rol, documento in cuentas:
            usuario = Usuario.objects.filter(correo__iexact=correo).first()
            creado = usuario is None
            if usuario is None:
                usuario = Usuario(
                    correo=correo,
                    nombre=nombre,
                    apellido=apellido,
                    tipo_documento="CC",
                    numero_documento=documento,
                )
            else:
                usuario.nombre = nombre
                usuario.apellido = apellido

            configurar_password = creado or options["reset_existing_passwords"]
            if configurar_password:
                if options["non_interactive"]:
                    password_env = password_envs[correo]
                    password = os.environ.get(password_env)
                    if not password:
                        raise CommandError(
                            f"Falta configurar la variable secreta {password_env}."
                        )
                else:
                    password = getpass.getpass(f"Nueva contraseña para {correo}: ")
                    confirmacion = getpass.getpass(f"Confirma la contraseña para {correo}: ")
                    if not password or password != confirmacion:
                        raise CommandError(f"La contraseña para {correo} está vacía o no coincide.")
                try:
                    validate_password(password, user=usuario)
                except ValidationError as exc:
                    raise CommandError(
                        f"La contraseña configurada para {correo} no cumple los requisitos: {exc}"
                    ) from exc
                passwords[correo] = password

        for correo, nombre, apellido, nombre_rol, documento in cuentas:
            usuario, _ = Usuario.objects.get_or_create(
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
            usuario.rol = Rol.objects.get(nombre=nombre_rol)
            usuario.is_active = True
            if correo in passwords:
                usuario.set_password(passwords[correo])

            with transaction.atomic():
                usuario.save()

            accion = "creada" if creado else "actualizada"
            self.stdout.write(self.style.SUCCESS(f"Cuenta {accion}: {correo} - Rol: {nombre_rol}"))
