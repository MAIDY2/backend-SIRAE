import datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from apps_sirae.roles.models import Rol
from apps_sirae.usuarios.models import Usuario
from apps_sirae.instituciones.models import Institucion, SupervisorInstitucion
from apps_sirae.sedes.models import Sede
from apps_sirae.contratos_pae.models import Contrato
from apps_sirae.jornadas.models import Jornada
from apps_sirae.grados.models import Grados, GrupoGramaje
from apps_sirae.sede_jornada.models import SedeJornada, SedeJornadaGrado
from apps_sirae.unidades_medida.models import UnidadMedida
from apps_sirae.tipos_mercado.models import TipoMercado
from apps_sirae.categorias_inventario.models import CategoriaInventario
from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.gramage.models import Gramage
from apps_sirae.facturas_compra.models import InventarioCentral, Proveedor, FacturaCompra, DetalleFacturaCompra


class Command(BaseCommand):
    help = "Puebla datos demo completos para probar el flujo de asignación, entregas y planillas."

    def handle(self, *args, **options):
        with transaction.atomic():
            # 1. Roles
            rol_super, _ = Rol.objects.get_or_create(
                nombre=Rol.NombreRol.SUPER_ADMINISTRADOR,
                defaults={"descripcion": "Gestión global de instituciones y stock central."},
            )
            rol_admin, _ = Rol.objects.get_or_create(
                nombre=Rol.NombreRol.ADMINISTRADOR,
                defaults={"descripcion": "Administración de sede y cupos."},
            )
            rol_supervisor, _ = Rol.objects.get_or_create(
                nombre=Rol.NombreRol.SUPERVISOR,
                defaults={"descripcion": "Supervisión y despachos de alimentos."},
            )
            rol_jefa, _ = Rol.objects.get_or_create(
                nombre="JefaManipuladoras",
                defaults={"descripcion": "Jefa de cocina de manipuladoras."},
            )
            rol_manip, _ = Rol.objects.get_or_create(
                nombre="Manipuladora",
                defaults={"descripcion": "Manipuladora de alimentos."},
            )

            # 2. Institución
            inst, _ = Institucion.objects.get_or_create(
                nombre_institucion="IE San José",
                defaults={
                    "nit": "900123456-1",
                    "telefono": "6041234567",
                    "correo_contacto": "contacto@iesanjose.edu.co",
                    "representante_legal": "Rector Carlos Mendoza",
                    "estado": "ACTIVO",
                },
            )

            # 3. Sedes
            sede_principal, _ = Sede.objects.get_or_create(
                id_institucion=inst,
                nombre_sede="Sede Principal",
                defaults={
                    "codigo_dane": "11900100001",
                    "direccion": "Calle 10 # 20-30",
                    "telefono": "6041234567",
                    "estado": "ACTIVO",
                },
            )

            sede_norte, _ = Sede.objects.get_or_create(
                id_institucion=inst,
                nombre_sede="Sede Norte",
                defaults={
                    "codigo_dane": "11900100002",
                    "direccion": "Carrera 45 # 70-15",
                    "telefono": "6047654321",
                    "estado": "ACTIVO",
                },
            )

            # 4. Usuarios
            password_demo = "Sirae2026**"

            superadmin, _ = Usuario.objects.get_or_create(
                correo="superadmin@sirae.com",
                defaults={
                    "nombre": "Super",
                    "apellido": "Admin",
                    "numero_documento": "SA1001",
                    "rol": rol_super,
                    "is_superuser": True,
                    "is_staff": True,
                    "is_active": True,
                    "debe_cambiar_password": False,
                },
            )
            superadmin.set_password(password_demo)
            superadmin.debe_cambiar_password = False
            superadmin.save()

            admin_user, _ = Usuario.objects.get_or_create(
                correo="admin@sirae.com",
                defaults={
                    "nombre": "Ana",
                    "apellido": "Mendoza",
                    "numero_documento": "ADM1001",
                    "rol": rol_admin,
                    "id_institucion": inst,
                    "is_active": True,
                    "debe_cambiar_password": False,
                },
            )
            admin_user.set_password(password_demo)
            admin_user.id_institucion = inst
            admin_user.debe_cambiar_password = False
            admin_user.save()

            supervisor_user, _ = Usuario.objects.get_or_create(
                correo="supervisor@sirae.com",
                defaults={
                    "nombre": "David",
                    "apellido": "Pérez",
                    "numero_documento": "SUP1001",
                    "rol": rol_supervisor,
                    "is_active": True,
                    "debe_cambiar_password": False,
                },
            )
            supervisor_user.set_password(password_demo)
            supervisor_user.debe_cambiar_password = False
            supervisor_user.save()
            SupervisorInstitucion.objects.get_or_create(
                id_supervisor=supervisor_user,
                id_institucion=inst,
            )

            jefa_user, _ = Usuario.objects.get_or_create(
                correo="jefe@sirae.com",
                defaults={
                    "nombre": "Marta",
                    "apellido": "Gómez",
                    "numero_documento": "JEF1001",
                    "rol": rol_jefa,
                    "id_institucion": inst,
                    "id_sede": sede_principal,
                    "is_active": True,
                    "debe_cambiar_password": False,
                },
            )
            jefa_user.set_password(password_demo)
            jefa_user.debe_cambiar_password = False
            jefa_user.save()

            # 5. Jornadas y Grados
            jornada_m, _ = Jornada.objects.get_or_create(
                nombre_jornada="Jornada Mañana",
            )

            grupo_primaria, _ = GrupoGramaje.objects.get_or_create(
                nombre="Primaria",
                defaults={"nivel_educativo": "PRIMARIA", "estado": "ACTIVO"},
            )
            grupo_secundaria, _ = GrupoGramaje.objects.get_or_create(
                nombre="Secundaria",
                defaults={"nivel_educativo": "SECUNDARIA", "estado": "ACTIVO"},
            )

            grado_prim, _ = Grados.objects.get_or_create(
                nombre_grado="Tercero Primaria",
                defaults={"id_grupo_gramaje": grupo_primaria, "nivel_educativo": "PRIMARIA", "estado": "ACTIVO"},
            )
            grado_sec, _ = Grados.objects.get_or_create(
                nombre_grado="Séptimo Secundaria",
                defaults={"id_grupo_gramaje": grupo_secundaria, "nivel_educativo": "SECUNDARIA", "estado": "ACTIVO"},
            )

            # Asignación de cupos por sede/jornada/grado (lo que hace el Administrador)
            sj_p, _ = SedeJornada.objects.get_or_create(
                id_sede=sede_principal,
                id_jornada=jornada_m,
                defaults={"cupos": 100},
            )
            sj_p.cupos = 100
            sj_p.save()

            SedeJornadaGrado.objects.get_or_create(
                id_sede_jornada=sj_p,
                id_grado=grado_prim,
                defaults={"cupos": 60, "estado": "ACTIVO"},
            )
            SedeJornadaGrado.objects.get_or_create(
                id_sede_jornada=sj_p,
                id_grado=grado_sec,
                defaults={"cupos": 40, "estado": "ACTIVO"},
            )

            sj_n, _ = SedeJornada.objects.get_or_create(
                id_sede=sede_norte,
                id_jornada=jornada_m,
                defaults={"cupos": 50},
            )
            sj_n.cupos = 50
            sj_n.save()

            SedeJornadaGrado.objects.get_or_create(
                id_sede_jornada=sj_n,
                id_grado=grado_prim,
                defaults={"cupos": 50, "estado": "ACTIVO"},
            )

            # 6. Contrato PAE
            hoy = datetime.date.today()
            fin_ano = datetime.date(hoy.year, 12, 31)
            contrato, _ = Contrato.objects.get_or_create(
                numero_cor="CTR-PAE-2026-ANT-01",
                defaults={
                    "institucion": inst.nombre_institucion,
                    "id_institucion": inst,
                    "zona": "Medellín Centro",
                    "fecha_inicio": hoy,
                    "fecha_fin": fin_ano,
                    "estado": "ACTIVO",
                    "cupos": 150,
                    "id_usuario_supervisor": supervisor_user,
                    "periodicidad_perecederos": "SEMANAL",
                    "periodicidad_no_perecederos": "MENSUAL",
                    "dias_cobertura_perecederos": 5,
                    "dias_cobertura_no_perecederos": 20,
                },
            )

            # 7. Unidades de Medida
            u_kg, _ = UnidadMedida.objects.get_or_create(
                abreviatura="kg",
                defaults={"nombre": "Kilogramo", "tipo_magnitud": "MASA", "factor_conversion_base": Decimal("1000.000000")},
            )
            u_g, _ = UnidadMedida.objects.get_or_create(
                abreviatura="g",
                defaults={"nombre": "Gramo", "tipo_magnitud": "MASA", "factor_conversion_base": Decimal("1.000000")},
            )
            u_l, _ = UnidadMedida.objects.get_or_create(
                abreviatura="L",
                defaults={"nombre": "Litro", "tipo_magnitud": "VOLUMEN", "factor_conversion_base": Decimal("1000.000000")},
            )
            u_ml, _ = UnidadMedida.objects.get_or_create(
                abreviatura="ml",
                defaults={"nombre": "Mililitro", "tipo_magnitud": "VOLUMEN", "factor_conversion_base": Decimal("1.000000")},
            )
            u_und, _ = UnidadMedida.objects.get_or_create(
                abreviatura="und",
                defaults={"nombre": "Unidad", "tipo_magnitud": "CANTIDAD", "factor_conversion_base": Decimal("1.000000")},
            )

            # Tipos de Mercado
            tm_no_per, _ = TipoMercado.objects.get_or_create(nombre_tipo="No Perecedero")
            tm_per, _ = TipoMercado.objects.get_or_create(nombre_tipo="Perecedero")

            # Categorías
            cat_granos, _ = CategoriaInventario.objects.get_or_create(nombre_categoria="Granos y Abarrotes")
            cat_carnes, _ = CategoriaInventario.objects.get_or_create(nombre_categoria="Cárnicos y Huevos")
            cat_lacteos, _ = CategoriaInventario.objects.get_or_create(nombre_categoria="Lácteos")
            cat_verduras, _ = CategoriaInventario.objects.get_or_create(nombre_categoria="Frutas y Verduras")

            # 8. Ingredientes y Gramajes
            arroz, _ = Ingrediente.objects.get_or_create(
                nombre_ingrediente="Arroz Blanco",
                defaults={
                    "id_unidad_medida": u_kg,
                    "id_tipo_mercado": tm_no_per,
                    "id_categoria_inventario": cat_granos,
                    "tipo_conservacion": "no_perecedero",
                    "marca_ingrediente": "Diana",
                },
            )
            frijol, _ = Ingrediente.objects.get_or_create(
                nombre_ingrediente="Fríjol Cargamanto",
                defaults={
                    "id_unidad_medida": u_kg,
                    "id_tipo_mercado": tm_no_per,
                    "id_categoria_inventario": cat_granos,
                    "tipo_conservacion": "no_perecedero",
                    "marca_ingrediente": "El Grano",
                },
            )
            pollo, _ = Ingrediente.objects.get_or_create(
                nombre_ingrediente="Pechuga de Pollo",
                defaults={
                    "id_unidad_medida": u_kg,
                    "id_tipo_mercado": tm_per,
                    "id_categoria_inventario": cat_carnes,
                    "tipo_conservacion": "perecedero",
                    "marca_ingrediente": "Pollo Fiesta",
                },
            )
            zanahoria, _ = Ingrediente.objects.get_or_create(
                nombre_ingrediente="Zanahoria",
                defaults={
                    "id_unidad_medida": u_kg,
                    "id_tipo_mercado": tm_per,
                    "id_categoria_inventario": cat_verduras,
                    "tipo_conservacion": "perecedero",
                },
            )
            leche, _ = Ingrediente.objects.get_or_create(
                nombre_ingrediente="Leche Entera Pasteurizada",
                defaults={
                    "id_unidad_medida": u_l,
                    "id_tipo_mercado": tm_per,
                    "id_categoria_inventario": cat_lacteos,
                    "tipo_conservacion": "perecedero",
                    "marca_ingrediente": "Colanta",
                },
            )

            # Gramajes según grupo/grado
            for ing, g_prim, g_sec in [
                (arroz, Decimal("45.0"), Decimal("60.0")),
                (frijol, Decimal("35.0"), Decimal("50.0")),
                (pollo, Decimal("60.0"), Decimal("85.0")),
                (zanahoria, Decimal("25.0"), Decimal("40.0")),
            ]:
                Gramage.objects.get_or_create(
                    id_ingrediente=ing,
                    id_grado=grado_prim,
                    defaults={"cantidad_gramaje": g_prim, "id_unidad_medida": u_g},
                )
                Gramage.objects.get_or_create(
                    id_ingrediente=ing,
                    id_grado=grado_sec,
                    defaults={"cantidad_gramaje": g_sec, "id_unidad_medida": u_g},
                )

            # Leche
            Gramage.objects.get_or_create(
                id_ingrediente=leche,
                id_grado=grado_prim,
                defaults={"cantidad_gramaje": Decimal("200.0"), "id_unidad_medida": u_ml},
            )
            Gramage.objects.get_or_create(
                id_ingrediente=leche,
                id_grado=grado_sec,
                defaults={"cantidad_gramaje": Decimal("200.0"), "id_unidad_medida": u_ml},
            )

            # 9. Proveedor e Inventario Central (Stock Global)
            prov, _ = Proveedor.objects.get_or_create(
                nombre="Distribuidora Mayorista del Valle",
                defaults={"nit": "800987654-3", "telefono": "6049998877", "estado": "ACTIVO"},
            )

            stocks = [
                (arroz, u_kg, Decimal("300.000"), Decimal("30.00")),
                (frijol, u_kg, Decimal("150.000"), Decimal("20.00")),
                (pollo, u_kg, Decimal("200.000"), Decimal("25.00")),
                (zanahoria, u_kg, Decimal("100.000"), Decimal("15.00")),
                (leche, u_l, Decimal("250.000"), Decimal("30.00")),
            ]

            for ing, u, cant, s_min in stocks:
                inv_c, _ = InventarioCentral.objects.get_or_create(
                    id_ingrediente=ing,
                    defaults={
                        "id_unidad_medida": u,
                        "cantidad_disponible": cant,
                        "stock_minimo": s_min,
                    },
                )
                inv_c.cantidad_disponible = cant
                inv_c.stock_minimo = s_min
                inv_c.save()

            self.stdout.write(self.style.SUCCESS("✓ Datos demo poblados exitosamente en la base de datos."))
            self.stdout.write("---------------------------------------------------------------------")
            self.stdout.write("Institución demo: IE San José (Sede Principal: 100 cupos | Sede Norte: 50 cupos)")
            self.stdout.write("Contrato demo: CTR-PAE-2026-ANT-01")
            self.stdout.write("Stock en Bodega Central: Arroz (300kg), Fríjol (150kg), Pollo (200kg), Zanahoria (100kg), Leche (250L)")
            self.stdout.write("---------------------------------------------------------------------")
            self.stdout.write("Credenciales de acceso (todas con contraseña: PaeSeguro2026*!):")
            self.stdout.write("  - SuperAdmin:   superadmin@sirae.com")
            self.stdout.write("  - Administrador: admin@sirae.com")
            self.stdout.write("  - Supervisor:    supervisor@sirae.com")
            self.stdout.write("  - Jefa Cocina:   jefe@sirae.com")
            self.stdout.write("---------------------------------------------------------------------")
