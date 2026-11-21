from django.db import migrations


def poblar_cupos_reales(apps, schema_editor):
    try:
        Institucion = apps.get_model('instituciones', 'Institucion')
        Sede = apps.get_model('sedes', 'Sede')
        Jornada = apps.get_model('jornadas', 'Jornada')
        Grados = apps.get_model('grados', 'Grados')
        Contrato = apps.get_model('contratos_pae', 'Contrato')
        SedeJornada = apps.get_model('sede_jornada', 'SedeJornada')
        SedeJornadaGrado = apps.get_model('sede_jornada', 'SedeJornadaGrado')
        Usuario = apps.get_model('usuarios', 'Usuario')
    except LookupError:
        return

    # 1. Obtener o asegurar jornada activa (por defecto Mañana)
    jornada = Jornada.objects.filter(estado='ACTIVO').first() or Jornada.objects.first()
    if not jornada:
        jornada = Jornada.objects.create(nombre_jornada='Mañana', estado='ACTIVO')

    # 2. Supervisor asignado
    supervisor = Usuario.objects.filter(rol__nombre__icontains='supervisor', is_active=True).first()

    # 3. Asignar cupos en base de datos para todas las instituciones activas y sus sedes
    instituciones = Institucion.objects.filter(estado='ACTIVO')
    for inst in instituciones:
        contratos = Contrato.objects.filter(id_institucion=inst)
        contrato_activo = contratos.filter(estado__in=['ACTIVO', 'Vigente', 'Activo']).first() or contratos.first()

        if not contrato_activo:
            contrato_activo = Contrato.objects.create(
                numero_cor=f"CTO-PAE-{inst.pk}-2026",
                institucion=inst.nombre_institucion,
                id_institucion=inst,
                id_jornada=jornada,
                id_usuario_supervisor=supervisor,
                cupos=300,
                periodicidad_perecederos='SEMANAL',
                dias_cobertura_perecederos=5,
                periodicidad_no_perecederos='MENSUAL',
                dias_cobertura_no_perecederos=20,
                estado='ACTIVO'
            )
        elif (contrato_activo.cupos or 0) <= 0:
            contrato_activo.cupos = 300
            contrato_activo.save(update_fields=['cupos'])

        sedes = Sede.objects.filter(id_institucion=inst, estado='ACTIVO')
        grados_activos = list(Grados.objects.filter(estado='ACTIVO')[:6])
        if not grados_activos:
            grados_activos = list(Grados.objects.all()[:6])

        cupos_por_sede = max(60, int((contrato_activo.cupos or 300) / max(1, sedes.count())))

        for sede in sedes:
            sj, _ = SedeJornada.objects.get_or_create(
                id_sede=sede,
                id_jornada=jornada,
                defaults={'cupos': cupos_por_sede}
            )
            if (sj.cupos or 0) <= 0:
                sj.cupos = cupos_por_sede
                sj.save(update_fields=['cupos'])

            if grados_activos:
                cupo_grado = max(10, int(sj.cupos / len(grados_activos)))
                for grado in grados_activos:
                    sjg, _ = SedeJornadaGrado.objects.get_or_create(
                        id_sede_jornada=sj,
                        id_grado=grado,
                        defaults={'cupos': cupo_grado, 'estado': 'ACTIVO'}
                    )
                    if (sjg.cupos or 0) <= 0:
                        sjg.cupos = cupo_grado
                        sjg.estado = 'ACTIVO'
                        sjg.save(update_fields=['cupos', 'estado'])


class Migration(migrations.Migration):

    dependencies = [
        ('sede_jornada', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(poblar_cupos_reales, migrations.RunPython.noop),
    ]
