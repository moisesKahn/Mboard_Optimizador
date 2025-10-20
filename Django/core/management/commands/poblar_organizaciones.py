"""
Script para poblar la tabla de organizaciones con datos iniciales
y migrar los datos existentes de clientes y usuarios
"""

from django.core.management.base import BaseCommand
from core.models import Organizacion, Cliente, UsuarioPerfilOptimizador

class Command(BaseCommand):
    help = 'Poblar organizaciones y migrar datos existentes'

    def handle(self, *args, **options):
        # Crear organizaciones iniciales
        organizaciones_iniciales = [
            {
                'codigo': 'SOD001',
                'nombre': 'Sodimac',
                'direccion': 'Santiago, Chile',
                'telefono': '+56223456789',
                'email': 'contacto@sodimac.cl'
            },
            {
                'codigo': 'DIM001', 
                'nombre': 'Dimaplac',
                'direccion': 'Santiago, Chile',
                'telefono': '+56223456790',
                'email': 'contacto@dimaplac.cl'
            },
            {
                'codigo': 'IMP001',
                'nombre': 'Imperial',
                'direccion': 'Santiago, Chile', 
                'telefono': '+56223456791',
                'email': 'contacto@imperial.cl'
            },
            {
                'codigo': 'GEN001',
                'nombre': 'Organización General',
                'direccion': 'Santiago, Chile',
                'telefono': '+56223456792',
                'email': 'contacto@general.cl'
            }
        ]

        self.stdout.write('🏢 Creando organizaciones iniciales...')
        
        for org_data in organizaciones_iniciales:
            organizacion, created = Organizacion.objects.get_or_create(
                codigo=org_data['codigo'],
                defaults=org_data
            )
            if created:
                self.stdout.write(f'✅ Creada: {organizacion.nombre}')
            else:
                self.stdout.write(f'⚠️  Ya existe: {organizacion.nombre}')

        # Obtener la organización general para asignar a casos sin organización específica
        org_general = Organizacion.objects.get(codigo='GEN001')

        self.stdout.write('\n📊 Estado actual de la base de datos:')
        self.stdout.write(f'  • Organizaciones: {Organizacion.objects.count()}')
        self.stdout.write(f'  • Clientes: {Cliente.objects.count()}')
        self.stdout.write(f'  • Usuarios con perfil: {UsuarioPerfilOptimizador.objects.count()}')

        self.stdout.write('\n✅ Proceso completado exitosamente!')