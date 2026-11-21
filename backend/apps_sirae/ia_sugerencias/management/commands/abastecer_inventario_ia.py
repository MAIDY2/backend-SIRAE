from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction

from apps_sirae.ingredientes.models import Ingrediente
from apps_sirae.inventario.models import Inventario
from apps_sirae.sedes.models import Sede
from apps_sirae.unidades_medida.models import UnidadMedida


INGREDIENTES_PAE_INICIALES = [
    # (nombre, abrev_unidad, nombre_unidad, magnitud, factor, cantidad_actual, stock_minimo)
    ("Huevos", "und", "Unidad", "UNIDAD", Decimal("1.0"), Decimal("600.00"), Decimal("100.00")),
    ("Arroz", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("80.00"), Decimal("15.00")),
    ("Pollo", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("50.00"), Decimal("10.00")),
    ("Carne de res", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("40.00"), Decimal("8.00")),
    ("Lentejas", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("30.00"), Decimal("6.00")),
    ("Frijoles", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("30.00"), Decimal("6.00")),
    ("Papa", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("60.00"), Decimal("12.00")),
    ("Yuca", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("40.00"), Decimal("8.00")),
    ("Plátano", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("35.00"), Decimal("8.00")),
    ("Harina de maíz", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("40.00"), Decimal("8.00")),
    ("Avena", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("25.00"), Decimal("5.00")),
    ("Queso", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("20.00"), Decimal("4.00")),
    ("Leche líquida", "L", "Litro", "VOLUMEN", Decimal("1000.0"), Decimal("120.00"), Decimal("20.00")),
    ("Yogurt", "L", "Litro", "VOLUMEN", Decimal("1000.0"), Decimal("60.00"), Decimal("10.00")),
    ("Chocolate", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("15.00"), Decimal("3.00")),
    ("Tomate", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("25.00"), Decimal("5.00")),
    ("Cebolla", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("20.00"), Decimal("4.00")),
    ("Zanahoria", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("25.00"), Decimal("5.00")),
    ("Cilantro", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("5.00"), Decimal("1.00")),
    ("Banano", "und", "Unidad", "UNIDAD", Decimal("1.0"), Decimal("400.00"), Decimal("60.00")),
    ("Mango", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("40.00"), Decimal("8.00")),
    ("Papaya", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("40.00"), Decimal("8.00")),
    ("Pan de queso", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("25.00"), Decimal("5.00")),
    ("Galleta", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("20.00"), Decimal("4.00")),
    ("Aceite vegetal", "L", "Litro", "VOLUMEN", Decimal("1000.0"), Decimal("20.00"), Decimal("4.00")),
    ("Azúcar", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("20.00"), Decimal("4.00")),
    ("Sal", "kg", "Kilogramo", "MASA", Decimal("1000.0"), Decimal("10.00"), Decimal("2.00")),
]


class Command(BaseCommand):
    help = "Asegura ingredientes básicos del PAE con stock suficiente en las sedes activas para generar recetas con IA."

    def add_arguments(self, parser):
        parser.add_argument(
            "--sede",
            type=int,
            default=None,
            help="ID de sede específica a abastecer (si se omite, abastece la sede 1 o todas las sedes activas).",
        )

    def handle(self, *args, **options):
        sede_id = options.get("sede")
        if sede_id:
            sedes = list(Sede.objects.filter(id_sede=sede_id))
        else:
            sedes = list(Sede.objects.filter(estado="ACTIVO").order_by("id_sede"))
            if not sedes:
                sedes = list(Sede.objects.all().order_by("id_sede"))

        if not sedes:
            self.stdout.write(self.style.WARNING("No se encontraron sedes registradas."))
            return

        with transaction.atomic():
            unidades_cache = {}
            for _, abrev, u_nombre, mag, factor, _, _ in INGREDIENTES_PAE_INICIALES:
                if abrev not in unidades_cache:
                    u_obj = UnidadMedida.objects.filter(abreviatura__iexact=abrev).first()
                    if not u_obj:
                        u_obj = UnidadMedida.objects.create(
                            nombre=u_nombre,
                            abreviatura=abrev,
                            tipo_magnitud=mag,
                            factor_conversion_base=factor,
                            estado="ACTIVO",
                        )
                    unidades_cache[abrev] = u_obj

            creados = 0
            actualizados = 0

            for sede in sedes:
                for nombre, abrev, _, _, _, cant_target, stock_min in INGREDIENTES_PAE_INICIALES:
                    u_obj = unidades_cache[abrev]
                    ing = Ingrediente.objects.filter(nombre_ingrediente__iexact=nombre).first()
                    if not ing:
                        ing = Ingrediente.objects.create(
                            nombre_ingrediente=nombre,
                            descripcion=f"{nombre} para preparaciones escolares PAE Colombia",
                            id_unidad_medida=u_obj,
                            tipo_conservacion="no_perecedero" if abrev != "L" else "perecedero",
                        )

                    inv = Inventario.objects.filter(
                        id_sede=sede,
                        id_ingrediente=ing.id_ingrediente,
                    ).first()

                    if inv:
                        # Solo reforzar si está por debajo del stock objetivo o con unidad inconsistente
                        necesita_ajuste = (
                            Decimal(str(inv.cantidad_actual or 0)) < cant_target
                            or inv.id_unidad_medida != u_obj.id_unidad_medida
                        )
                        if necesita_ajuste:
                            inv.cantidad_actual = cant_target
                            inv.stock_minimo = max(Decimal(str(inv.stock_minimo or 0)), stock_min)
                            inv.id_unidad_medida = u_obj.id_unidad_medida
                            if not inv.id_institucion_id and sede.id_institucion_id:
                                inv.id_institucion_id = sede.id_institucion_id
                            inv.save()
                            actualizados += 1
                    else:
                        Inventario.objects.create(
                            id_sede=sede,
                            id_institucion_id=sede.id_institucion_id,
                            id_ingrediente=ing.id_ingrediente,
                            cantidad_actual=cant_target,
                            stock_minimo=stock_min,
                            id_unidad_medida=u_obj.id_unidad_medida,
                        )
                        creados += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Inventario PAE listo en {len(sedes)} sede(s): {creados} creados, {actualizados} actualizados."
            )
        )
