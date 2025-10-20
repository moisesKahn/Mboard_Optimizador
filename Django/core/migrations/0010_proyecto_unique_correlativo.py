from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_backfill_proyecto_correlativo'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='proyecto',
            unique_together={('cliente', 'correlativo')},
        ),
    ]
