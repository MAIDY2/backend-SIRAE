from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from apps_sirae.contratos_pae.models import Contrato, DistribucionGrado, DistribucionSede
from apps_sirae.contratos_seccion_menu.models import ContratoSeccionMenu
from apps_sirae.instituciones.models import Institucion
from apps_sirae.menus.models import Menu


class Command(BaseCommand):
    help = (
        "Detecta instituciones con múltiples contratos PAE y consolida de forma segura "
        "todas las relaciones en un único contrato principal. Por defecto corre en modo "
        "simulación (dry-run); pase --aplicar para ejecutar los cambios."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar',
            action='store_true',
            help='Aplica la consolidación y elimina los contratos duplicados en la base de datos.',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']
        grupos = self._agrupar_contratos_por_institucion()
        duplicados = {k: v for k, v in grupos.items() if len(v) > 1}

        if not duplicados:
            self.stdout.write(self.style.SUCCESS("No se encontraron instituciones con contratos duplicados."))
            return

        self.stdout.write(
            self.style.WARNING(
                f"Se encontraron {len(duplicados)} institución(es) con contratos duplicados "
                f"({'APLICANDO CAMBIOS' if aplicar else 'MODO SIMULACIÓN / DRY-RUN'}):"
            )
        )

        total_eliminados = 0
        for clave, contratos in duplicados.items():
            principal, secundarios = self._elegir_principal(contratos)
            nombre_ie = (
                principal.institucion
                or (principal.id_institucion.nombre_institucion if principal.id_institucion else str(clave))
            )
            self.stdout.write(
                f"\n• {nombre_ie}: mantener id={principal.id_contrato} ({principal.numero_cor}, estado={principal.estado}, cupos={principal.cupos})"
            )
            for sec in secundarios:
                self.stdout.write(
                    f"  - consolidar y eliminar id={sec.id_contrato} ({sec.numero_cor}, estado={sec.estado}, cupos={sec.cupos})"
                )

            if aplicar:
                self._consolidar_grupo(principal, secundarios)
                total_eliminados += len(secundarios)

        if aplicar:
            self.stdout.write(
                self.style.SUCCESS(f"\nLimpieza completada. Contratos duplicados eliminados: {total_eliminados}.")
            )
        else:
            self.stdout.write(
                self.style.NOTICE("\nSimulación finalizada. Ejecuta con --aplicar para consolidar estos contratos.")
            )

    def _agrupar_contratos_por_institucion(self):
        mapa_nombres = {
            inst.nombre_institucion.strip().lower(): inst.id_institucion
            for inst in Institucion.objects.all()
            if inst.nombre_institucion
        }
        grupos = defaultdict(list)

        for c in Contrato.objects.select_related('id_institucion').order_by('id_contrato'):
            inst_id = c.id_institucion_id
            nombre_norm = (c.institucion or '').strip().lower()
            if inst_id is None and nombre_norm in mapa_nombres:
                inst_id = mapa_nombres[nombre_norm]

            if inst_id is not None:
                grupos[('id', inst_id)].append(c)
            elif nombre_norm:
                grupos[('name', nombre_norm)].append(c)

        return grupos

    def _puntaje_contrato(self, contrato):
        estado = (contrato.estado or '').strip().lower()
        es_activo = 1 if estado == 'activo' else 0
        rel_count = (
            DistribucionSede.objects.filter(id_contrato=contrato).count()
            + ContratoSeccionMenu.objects.filter(id_contrato=contrato).count()
            + Menu.objects.filter(id_contrato=contrato.id_contrato).count()
        )
        for rel in Contrato._meta.related_objects:
            if rel.related_model in (DistribucionSede, ContratoSeccionMenu):
                continue
            rel_count += rel.related_model.objects.filter(**{rel.field.name: contrato}).count()

        return (
            es_activo,
            rel_count,
            1 if contrato.id_usuario_supervisor_id else 0,
            1 if contrato.id_institucion_id else 0,
            contrato.cupos or 0,
            -contrato.id_contrato,
        )

    def _elegir_principal(self, contratos):
        ordenados = sorted(contratos, key=self._puntaje_contrato, reverse=True)
        return ordenados[0], ordenados[1:]

    @transaction.atomic
    def _consolidar_grupo(self, principal, secundarios):
        campos_actualizados = []
        if principal.id_institucion_id is None:
            for sec in secundarios:
                if sec.id_institucion_id is not None:
                    principal.id_institucion_id = sec.id_institucion_id
                    campos_actualizados.append('id_institucion')
                    break
        if principal.id_usuario_supervisor_id is None:
            for sec in secundarios:
                if sec.id_usuario_supervisor_id is not None:
                    principal.id_usuario_supervisor_id = sec.id_usuario_supervisor_id
                    campos_actualizados.append('id_usuario_supervisor')
                    break
        if campos_actualizados:
            principal.save(update_fields=campos_actualizados)

        for sec in secundarios:
            # 1. DistribucionSede (respeta unique_together id_contrato + id_sede)
            for ds in DistribucionSede.objects.filter(id_contrato=sec):
                existente = DistribucionSede.objects.filter(
                    id_contrato=principal, id_sede_id=ds.id_sede_id
                ).first()
                if existente is None:
                    ds.id_contrato = principal
                    ds.save(update_fields=['id_contrato'])
                else:
                    if existente.cupos_asignados == 0 and ds.cupos_asignados > 0:
                        existente.cupos_asignados = ds.cupos_asignados
                        existente.save(update_fields=['cupos_asignados'])
                        for dg in DistribucionGrado.objects.filter(id_distribucion_sede=ds):
                            DistribucionGrado.objects.update_or_create(
                                id_distribucion_sede=existente,
                                id_grado_id=dg.id_grado_id,
                                defaults={'cupos_asignados': dg.cupos_asignados},
                            )
                    ds.delete()

            # 2. ContratoSeccionMenu (db_constraint=False)
            secciones_principales = set(
                ContratoSeccionMenu.objects.filter(id_contrato=principal).values_list('id_seccion_id', flat=True)
            )
            for csm in ContratoSeccionMenu.objects.filter(id_contrato=sec):
                if csm.id_seccion_id not in secciones_principales:
                    csm.id_contrato = principal
                    csm.save(update_fields=['id_contrato'])
                    secciones_principales.add(csm.id_seccion_id)
                else:
                    csm.delete()

            # 3. Menus (IntegerField id_contrato)
            Menu.objects.filter(id_contrato=sec.id_contrato).update(id_contrato=principal.id_contrato)

            # 4. Resto de ForeignKeys hacia Contrato (entregas, inventario, reportes, etc.)
            for rel in Contrato._meta.related_objects:
                if rel.related_model in (DistribucionSede, ContratoSeccionMenu):
                    continue
                rel.related_model.objects.filter(**{rel.field.name: sec}).update(**{rel.field.name: principal})

            sec.delete()
