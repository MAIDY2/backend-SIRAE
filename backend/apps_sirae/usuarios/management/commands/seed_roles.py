from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from apps_sirae.usuarios.models import Rol, Usuario


class Command(BaseCommand):
    help = 'Inicializa y asegura los 4 roles oficiales del PAE en la base de datos de SIRAE'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Verificando y sincronizando roles oficiales del PAE..."))

        roles_data = [
            {
                'nombre_rol': 'Supervisor',
                'alias': 'supervisor',
                'descripcion': 'Registra entregas, entradas de inventario, fechas, cantidades y observaciones. Consulta consumos y reportes. No define la preparación del día ni registra el avance de cocina.'
            },
            {
                'nombre_rol': 'Administrador',
                'alias': 'admin',
                'descripcion': 'Configura usuarios, parámetros generales, productos, unidades de medida, periodos y permisos. Supervisa la operación global. No selecciona el menú diario ni reemplaza la función operativa de la jefa.'
            },
            {
                'nombre_rol': 'Jefa de manipuladoras',
                'alias': 'jefa',
                'descripcion': 'Registra la asistencia diaria, revisa sugerencias de IA, selecciona el menú del mes y de cada día, consulta y genera reportes.'
            },
            {
                'nombre_rol': 'Manipuladora de alimentos',
                'alias': 'manipuladora',
                'descripcion': 'Consulta el menú asignado, las cantidades calculadas, el proceso de preparación, el inventario disponible y registra el avance de cada componente.'
            },
        ]

        # Verificar si existe el rol 1 (Supervisor)
        try:
            rol_supervisor = Rol.objects.get(id_rol=1)
            rol_supervisor.nombre_rol = 'Supervisor'
            rol_supervisor.descripcion = roles_data[0]['descripcion']
            rol_supervisor.save()
            self.stdout.write(self.style.SUCCESS("Rol ID 1 sincronizado: 'Supervisor'."))
        except Rol.DoesNotExist:
            rol_1 = Rol.objects.create(
                id_rol=1,
                nombre_rol=roles_data[0]['nombre_rol'],
                descripcion=roles_data[0]['descripcion']
            )
            self.stdout.write(self.style.SUCCESS(f"Rol creado: {rol_1.nombre_rol} (ID: {rol_1.id_rol})"))

        # Crear o actualizar los otros 3 roles
        for r_info in roles_data[1:]:
            rol_existente = Rol.objects.filter(nombre_rol__iexact=r_info['nombre_rol']).first()
            if not rol_existente:
                nuevo_rol = Rol.objects.create(
                    nombre_rol=r_info['nombre_rol'],
                    descripcion=r_info['descripcion']
                )
                self.stdout.write(self.style.SUCCESS(f"Rol creado: {nuevo_rol.nombre_rol} (ID: {nuevo_rol.id_rol})"))
            else:
                rol_existente.descripcion = r_info['descripcion']
                rol_existente.save()
                self.stdout.write(self.style.SUCCESS(f"Rol verificado: {rol_existente.nombre_rol} (ID: {rol_existente.id_rol})"))

        # Verificar si existe al menos un usuario Administrador
        rol_admin = Rol.objects.filter(nombre_rol__icontains='administrador').first()
        admin_user = Usuario.objects.filter(id_rol=rol_admin).first() if rol_admin else None

        if not admin_user and rol_admin:
            self.stdout.write(self.style.WARNING("No se encontró ningún usuario con rol Administrador."))
            self.stdout.write(self.style.NOTICE("Creando usuario Administrador inicial..."))
            admin_nuevo = Usuario.objects.create(
                nombre_completo='Administrador del Sistema',
                email='admin@sirae.edu.co',
                password=make_password('Admin123*'),
                estado='Activo',
                documento_identidad='1000000000',
                id_rol=rol_admin
            )
            self.stdout.write(self.style.SUCCESS(
                f"Usuario Administrador creado exitosamente:\n"
                f"  - Correo: {admin_nuevo.email}\n"
                f"  - Contraseña temporal: Admin123*\n"
                f"  - Documento: {admin_nuevo.documento_identidad}"
            ))

        self.stdout.write(self.style.SUCCESS("\nSincronización de roles completada con éxito."))
