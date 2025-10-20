from django.db import migrations


def backfill_correlativos(apps, schema_editor):
    Proyecto = apps.get_model('core', 'Proyecto')
    # Construir correlativo incremental por cliente ordenado por fecha_creacion
    qs = Proyecto.objects.all().order_by('cliente_id', 'fecha_creacion', 'id')
    last_cliente = None
    counter = 0
    for p in qs.iterator():
        if p.cliente_id != last_cliente:
            last_cliente = p.cliente_id
            counter = 0
        # Si ya tiene un correlativo > 0, respetar; si es 0 o None, asignar siguiente
        if not p.correlativo or p.correlativo <= 0:
            counter += 1
            p.correlativo = counter
            p.save(update_fields=['correlativo'])
        else:
            # Mantener el contador al menos en el correlativo actual
            if p.correlativo > counter:
                counter = p.correlativo


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_proyecto_folio_fields'),
    ]

    operations = [
        migrations.RunPython(backfill_correlativos, migrations.RunPython.noop),
    ]
