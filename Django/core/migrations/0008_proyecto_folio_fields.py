from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_alter_material_organizacion_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='proyecto',
            name='correlativo',
            field=models.IntegerField(default=0, verbose_name='Correlativo'),
        ),
        migrations.AddField(
            model_name='proyecto',
            name='version',
            field=models.IntegerField(default=0, verbose_name='Versión'),
        ),
    ]
