from django.core.management.base import BaseCommand
from apps_sirae.roles.models import Rol


class Command(BaseCommand):
    help = "Inicializa los cuatro roles oficiales del PAE."

    def handle(self, *args, **options):
        roles = [
            ("Administrador", "Configura usuarios y parámetros generales del sistema."),
            ("supervisor", "Supervisa manipuladoras y procesos del PAE."),
            ("JefaManipuladoras", "Gestiona manipuladoras y menús."),
            ("Manipuladora", "Consulta y registra procesos asignados."),
        ]
        for nombre, descripcion in roles:
            rol, creado = Rol.objects.update_or_create(
                nombre=nombre,
                defaults={"descripcion": descripcion},
            )
            accion = "creado" if creado else "verificado"
            self.stdout.write(self.style.SUCCESS(f"Rol {accion}: {rol.nombre}"))
