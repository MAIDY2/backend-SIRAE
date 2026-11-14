from django.db import migrations


def limpiar_y_asegurar_secciones_canonicas(apps, schema_editor):
    SeccionMenu = apps.get_model('secciones_menu', 'SeccionMenu')
    ContratoSeccionMenu = apps.get_model('contratos_seccion_menu', 'ContratoSeccionMenu')
    Jornada = apps.get_model('jornadas', 'Jornada')

    # Nombres de secciones de prueba a eliminar
    nombres_prueba = ['prueba1', 'prueba2', 'sena', 'prueba 1', 'prueba 2', 'test', 'prueba']

    for nom in nombres_prueba:
        secciones_a_borrar = SeccionMenu.objects.filter(nombre_seccion__icontains=nom)
        for sp in secciones_a_borrar:
            ContratoSeccionMenu.objects.filter(id_seccion=sp).delete()
            sp.delete()

    # Jornadas sugeridas
    j_manana = Jornada.objects.filter(nombre_jornada__icontains='mañana').first()
    j_tarde = Jornada.objects.filter(nombre_jornada__icontains='tarde').first()
    j_unica = Jornada.objects.filter(nombre_jornada__icontains='única').first() or Jornada.objects.filter(nombre_jornada__icontains='unica').first()

    todas_jornadas = list(Jornada.objects.all().order_by('id_jornada'))
    if not j_manana and len(todas_jornadas) > 0:
        j_manana = todas_jornadas[0]
    if not j_unica:
        j_unica = j_manana
    if not j_tarde and len(todas_jornadas) > 1:
        j_tarde = todas_jornadas[1]
    elif not j_tarde:
        j_tarde = j_manana

    # Las 3 secciones canónicas oficiales del PAE
    canonicas = [
        {'id': 1, 'nombre': 'Desayuno', 'jornada': j_manana},
        {'id': 2, 'nombre': 'Almuerzo', 'jornada': j_unica},
        {'id': 3, 'nombre': 'Merienda', 'jornada': j_tarde},
    ]

    for item in canonicas:
        sec = SeccionMenu.objects.filter(id_seccion=item['id']).first()
        if sec:
            sec.nombre_seccion = item['nombre']
            if item['jornada']:
                sec.id_jornada = item['jornada']
            sec.save()
        else:
            por_nombre = SeccionMenu.objects.filter(nombre_seccion__iexact=item['nombre']).first()
            if por_nombre:
                por_nombre.nombre_seccion = item['nombre']
                if item['jornada']:
                    por_nombre.id_jornada = item['jornada']
                por_nombre.save()
            else:
                SeccionMenu.objects.create(
                    id_seccion=item['id'],
                    nombre_seccion=item['nombre'],
                    id_jornada=item['jornada'],
                )


class Migration(migrations.Migration):

    dependencies = [
        ('secciones_menu', '0004_alter_seccionmenu_id_jornada'),
    ]

    operations = [
        migrations.RunPython(limpiar_y_asegurar_secciones_canonicas, migrations.RunPython.noop),
    ]
