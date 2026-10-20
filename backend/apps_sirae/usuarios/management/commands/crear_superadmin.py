import os
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps_sirae.roles.models import Rol
from apps_sirae.usuarios.models import Usuario


class Command(BaseCommand):
    help = "Crea el Super Administrador inicial de forma idempotente leyendo credenciales de .env."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-reset-password",
            action="store_true",
            help="Fuerza el restablecimiento de la contraseña del Super Administrador existente.",
        )

    def handle(self, *args, **options):
        # 1. Asegurar la existencia del Rol oficial
        rol_super, _ = Rol.objects.get_or_create(
            nombre=Rol.NombreRol.SUPER_ADMINISTRADOR,
            defaults={"descripcion": "Gestión global de instituciones, contratos, catálogo y auditoría."}
        )

        # 2. Leer credenciales desde variables de entorno (.env)
        email = os.environ.get("SIRAE_SUPERADMIN_EMAIL", "superadmin@sirae.com").strip().lower()
        password = os.environ.get("SIRAE_SUPERADMIN_PASSWORD")

        if not password:
            raise CommandError(
                "No se encontró la variable de entorno 'SIRAE_SUPERADMIN_PASSWORD'. "
                "Por favor configúrala en el archivo .env antes de ejecutar este comando."
            )

        if len(password) < 6:
            raise CommandError("La contraseña configurada en SIRAE_SUPERADMIN_PASSWORD debe tener al menos 6 caracteres.")

        # 3. Comprobar si ya existe un Super Administrador (Idempotencia)
        superadmin_existente = Usuario.objects.filter(rol=rol_super).first()
        if not superadmin_existente:
            superadmin_existente = Usuario.objects.filter(correo__iexact=email).first()

        if superadmin_existente:
            if options["force_reset_password"]:
                superadmin_existente.set_password(password)
                superadmin_existente.debe_cambiar_password = True
                superadmin_existente.is_active = True
                superadmin_existente.is_staff = True
                superadmin_existente.is_superuser = True
                superadmin_existente.rol = rol_super
                superadmin_existente.save()
                self.stdout.write(
                    self.style.WARNING(
                        f"Contraseña del Super Administrador ({superadmin_existente.correo}) "
                        "restablecida exitosamente con obligación de cambio en el próximo login."
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"El Super Administrador ya existe ({superadmin_existente.correo}). "
                        "Operación idempotente: no se requirieron cambios."
                    )
                )
            return

        # 4. Crear el Super Administrador inicial
        with transaction.atomic():
            nuevo_superadmin = Usuario(
                correo=email,
                nombre="Super",
                apellido="Administrador",
                tipo_documento="CC",
                numero_documento="SUPER001",
                rol=rol_super,
                is_active=True,
                is_staff=True,
                is_superuser=True,
                debe_cambiar_password=True,
            )
            nuevo_superadmin.set_password(password)
            nuevo_superadmin.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Super Administrador inicial creado exitosamente: {email}\n"
                f"- Obligación de cambio de contraseña en primer login: ACTIVA\n"
                f"- Rol: {rol_super.get_nombre_display()}"
            )
        )
