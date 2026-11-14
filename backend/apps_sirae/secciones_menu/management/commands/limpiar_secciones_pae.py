from django.core.management.base import BaseCommand
from django.db import transaction

from apps_sirae.secciones_menu.models import SeccionMenu
from apps_sirae.contratos_seccion_menu.models import ContratoSeccionMenu
from apps_sirae.jornadas.models import Jornada


class Command(BaseCommand):
    help = "Limpia secciones de prueba (prueba1, prueba2, sena) y asegura las 3 secciones canónicas del PAE."

    def handle(self, *args, **options):
        with transaction.atomic():
            nombres_prueba = ['prueba1', 'prueba2', 'sena', 'prueba 1', 'prueba 2', 'test', 'prueba']

            eliminadas = 0
            for nom in nombres_prueba:
                secciones_a_borrar = SeccionMenu.objects.filter(nombre_seccion__icontains=nom)
                for sp in secciones_a_borrar:
                    ContratoSeccionMenu.objects.filter(id_seccion=sp).delete()
                    sp.delete()
                    eliminadas += 1

            self.stdout.write(self.style.SUCCESS(f"Se eliminaron {eliminadas} secciones de prueba o referencias."))

            j_manana = Jornada.objects.filter(nombre_jornada__icontains='mañana').first()
            j_tarde = Jornada.objects.filter(nombre_jornada__icontains='tarde').first()
            j_unica = Jornada.objects.filter(nombre_jornada__icontains='única').first() or Jornada.objects.filter(nombre_jornada__icontains='unica').first()

            todas = list(Jornada.objects.all().order_by('id_jornada'))
            if not j_manana and todas:
                j_manana = todas[0]
            if not j_unica:
                j_unica = j_manana
            if not j_tarde and len(todas) > 1:
                j_tarde = todas[1]
            elif not j_tarde:
                j_tarde = j_manana

            canonicas = [
                (1, 'Desayuno', j_manana),
                (2, 'Almuerzo', j_unica),
                (3, 'Merienda', j_tarde),
            ]

            for id_sec, nombre, jornada in canonicas:
                sec = SeccionMenu.objects.filter(id_seccion=id_sec).first()
                if sec:
                    sec.nombre_seccion = nombre
                    if jornada:
                        sec.id_jornada = jornada
                    sec.save()
                    self.stdout.write(f"Actualizada sección canónica ID {id_sec}: {nombre}")
                else:
                    por_nombre = SeccionMenu.objects.filter(nombre_seccion__iexact=nombre).first()
                    if por_nombre:
                        por_nombre.nombre_seccion = nombre
                        if jornada:
                            por_nombre.id_jornada = jornada
                        por_nombre.save()
                        self.stdout.write(f"Actualizada sección existente {nombre} a canónica.")
                    else:
                        SeccionMenu.objects.create(
                            id_seccion=id_sec,
                            nombre_seccion=nombre,
                            id_jornada=jornada,
                        )
                        self.stdout.write(self.style.SUCCESS(f"Creada sección canónica ID {id_sec}: {nombre}"))

        self.stdout.write(self.style.SUCCESS("Limpieza y configuración de secciones canónicas completada con éxito."))
