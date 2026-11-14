import os
from django.core.management.base import BaseCommand
from django.db import transaction

from apps_sirae.roles.models import Rol
from apps_sirae.usuarios.models import Usuario


class Command(BaseCommand):
    help = (
        "Crea o actualiza un usuario oficial como Administrador (superuser / is_staff = True) "
        "con el rol de administración correspondiente en SIRAE PAE."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            type=str,
            default="jhonriveracaicedo@gmail.com",
            help="Correo electrónico del administrador.",
        )
        parser.add_argument(
            "--nombre",
            type=str,
            default="Jhon",
            help="Nombre del administrador.",
        )
        parser.add_argument(
            "--apellido",
            type=str,
            default="Rivera Caicedo",
            help="Apellido del administrador.",
        )
        parser.add_argument(
            "--password",
            type=str,
            default=None,
            help="Contraseña inicial para la cuenta (si se crea nueva o con --reset-password).",
        )
        parser.add_argument(
            "--rol",
            type=str,
            default="Administrador",
            help="Nombre del rol a asignar (por defecto 'Administrador').",
        )
        parser.add_argument(
            "--documento",
            type=str,
            default="1000000001",
            help="Número de documento de identidad.",
        )
        parser.add_argument(
            "--tipo-documento",
            type=str,
            default="CC",
            help="Tipo de documento (por defecto 'CC').",
        )
        parser.add_argument(
            "--reset-password",
            action="store_true",
            help="Fuerza la actualización de la contraseña si el usuario ya existe.",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        nombre = options["nombre"].strip()
        apellido = options["apellido"].strip()
        rol_nombre = options["rol"].strip()
        num_doc = options["documento"].strip()
        tipo_doc = options["tipo_documento"].strip()
        reset_pwd = options["reset_password"]
        raw_password = options["password"]

        if not raw_password:
            raw_password = (
                os.environ.get("ADMIN_PASSWORD")
                or os.environ.get("SIRAE_SUPERADMIN_PASSWORD")
                or "AdminSirae2026*!"
            )

        # 1. Asegurar que exista el rol correspondiente
        rol, _ = Rol.objects.get_or_create(
            nombre=rol_nombre,
            defaults={
                "descripcion": (
                    "Control y gestión integral de usuarios, sedes, menús, "
                    "inventario y reportes del PAE."
                )
            },
        )

        with transaction.atomic():
            usuario = Usuario.objects.filter(correo__iexact=email).first()

            if usuario:
                usuario.rol = rol
                usuario.is_staff = True
                usuario.is_superuser = True
                usuario.is_active = True
                if not usuario.nombre:
                    usuario.nombre = nombre
                if not usuario.apellido:
                    usuario.apellido = apellido

                campos_actualizados = [
                    "rol",
                    "is_staff",
                    "is_superuser",
                    "is_active",
                    "nombre",
                    "apellido",
                ]

                if reset_pwd:
                    usuario.set_password(raw_password)
                    campos_actualizados.append("password")

                usuario.save(update_fields=campos_actualizados)
                accion_msg = "actualizado exitosamente"
            else:
                doc_final = num_doc
                if Usuario.objects.filter(numero_documento=doc_final).exists():
                    doc_final = f"ADMIN-{Usuario.objects.count() + 1}"

                usuario = Usuario.objects.create(
                    correo=email,
                    nombre=nombre,
                    apellido=apellido,
                    tipo_documento=tipo_doc,
                    numero_documento=doc_final,
                    rol=rol,
                    is_active=True,
                    is_staff=True,
                    is_superuser=True,
                    debe_cambiar_password=False,
                )
                usuario.set_password(raw_password)
                usuario.save()
                accion_msg = "creado exitosamente"

        self.stdout.write(self.style.SUCCESS("=" * 65))
        self.stdout.write(
            self.style.SUCCESS(
                f"[OK] Usuario Administrador {accion_msg}: {usuario.correo}"
            )
        )
        self.stdout.write(self.style.SUCCESS(f" - Nombre Completo: {usuario.nombre_completo}"))
        self.stdout.write(self.style.SUCCESS(f" - Rol Asignado   : {usuario.rol.nombre}"))
        self.stdout.write(self.style.SUCCESS(f" - is_staff       : {usuario.is_staff}"))
        self.stdout.write(self.style.SUCCESS(f" - is_superuser   : {usuario.is_superuser}"))
        self.stdout.write(self.style.SUCCESS(f" - is_active      : {usuario.is_active}"))
        self.stdout.write(self.style.SUCCESS(f" - es_admin()     : {usuario.es_administrador()}"))
        self.stdout.write(self.style.SUCCESS(f" - es_superadmin(): {usuario.es_super_administrador()}"))
        if accion_msg == "creado exitosamente" or reset_pwd:
            self.stdout.write(
                self.style.NOTICE(f" - Contraseña      : {raw_password}")
            )
        self.stdout.write(self.style.SUCCESS("=" * 65))
