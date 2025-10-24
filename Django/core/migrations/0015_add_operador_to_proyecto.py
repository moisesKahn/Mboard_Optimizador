"""Add operador FK to Proyecto and introduce operador role.

Revision ID: 0015_add_operador_to_proyecto
Revises: 0014_usuarioperfiloptimizador_must_change_password
Create Date: 2025-10-24 00:00
"""
from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0014_usuarioperfiloptimizador_must_change_password'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='proyecto',
            name='operador',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='proyectos_operador', to=settings.AUTH_USER_MODEL, verbose_name='Operador'),
        ),
    ]