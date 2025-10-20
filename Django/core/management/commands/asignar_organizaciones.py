"""
Script para asignar organizaciones a clientes y usuarios existentes
"""

from django.core.management.base import BaseCommand
from core.models import Organizacion, Cliente, UsuarioPerfilOptimizador
import random

class Command(BaseCommand):
    help = 'Asignar organizaciones a clientes y usuarios existentes'

    def handle(self, *args, **options):
        # Obtener organizaciones disponibles (excluyendo la general)
        organizaciones = list(Organizacion.objects.exclude(codigo='GEN001'))
        org_general = Organizacion.objects.get(codigo='GEN001')
        
        self.stdout.write('🏢 Asignando organizaciones a clientes existentes...')
        
        # Asignar organizaciones a clientes de manera distribuida
        clientes = Cliente.objects.filter(organizacion__isnull=True)
        for i, cliente in enumerate(clientes):
            # Distribuir equitativamente entre las organizaciones principales
            org_asignada = organizaciones[i % len(organizaciones)]
            cliente.organizacion = org_asignada
            cliente.save()
            self.stdout.write(f'✅ {cliente.nombre} → {org_asignada.nombre}')

        self.stdout.write('\n👥 Asignando organizaciones a usuarios existentes...')
        
        # Asignar organizaciones a usuarios (excepto super admins)
        usuarios = UsuarioPerfilOptimizador.objects.filter(organizacion__isnull=True)
        
        for usuario in usuarios:
            if usuario.rol == 'admin' and usuario.user.username == 'admin':
                # Super admin no necesita organización
                self.stdout.write(f'⚠️  Super Admin {usuario.user.username} → Sin organización (como debe ser)')
                continue
            elif usuario.rol == 'admin':
                # Admin regular asignar a organización general
                usuario.organizacion = org_general
                usuario.save()
                self.stdout.write(f'👑 Admin {usuario.user.get_full_name()} → {org_general.nombre}')
            else:
                # Operadores y otros roles distribuir entre organizaciones
                org_asignada = organizaciones[hash(usuario.user.username) % len(organizaciones)]
                usuario.organizacion = org_asignada
                usuario.save()
                self.stdout.write(f'👤 {usuario.user.get_full_name()} → {org_asignada.nombre}')

        # Mostrar resumen final
        self.stdout.write('\n📊 RESUMEN FINAL DE ASIGNACIONES:')
        
        for org in Organizacion.objects.all():
            clientes_count = Cliente.objects.filter(organizacion=org).count()
            usuarios_count = UsuarioPerfilOptimizador.objects.filter(organizacion=org).count()
            self.stdout.write(f'  🏢 {org.nombre}:')
            self.stdout.write(f'    • Clientes: {clientes_count}')
            self.stdout.write(f'    • Usuarios: {usuarios_count}')
        
        # Usuarios sin organización (super admins)
        usuarios_sin_org = UsuarioPerfilOptimizador.objects.filter(organizacion__isnull=True).count()
        if usuarios_sin_org > 0:
            self.stdout.write(f'  🔑 Super Admins sin organización: {usuarios_sin_org}')

        self.stdout.write('\n✅ Asignación de organizaciones completada exitosamente!')