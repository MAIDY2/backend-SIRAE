from django.db import migrations, models


def marcar_entregas_pendientes_preacreditadas(apps, schema_editor):
    Entrega = apps.get_model('entregas', 'Entrega')
    Entrega.objects.filter(estado='EN_TRANSITO').update(
        inventario_preacreditado=True
    )


class Migration(migrations.Migration):

    dependencies = [
        ('entregas', '0004_entrega_cantidad_rechazada_entrega_cantidad_recibida_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='entrega',
            name='inventario_preacreditado',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            marcar_entregas_pendientes_preacreditadas,
            migrations.RunPython.noop,
        ),
    ]
