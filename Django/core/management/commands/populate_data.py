from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from core.models import Cliente, Material, Tapacanto, Proyecto, UsuarioPerfilOptimizador
from datetime import date, datetime
import random

class Command(BaseCommand):
    help = 'Poblar la base de datos con datos de ejemplo para el sistema Optimizador'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Iniciando población de datos...'))

        # Crear superusuario si no existe
        if not User.objects.filter(username='admin').exists():
            admin_user = User.objects.create_superuser(
                username='admin',
                email='admin@optimizador.com',
                password='admin123',
                first_name='Administrador',
                last_name='Sistema'
            )
            UsuarioPerfilOptimizador.objects.create(
                user=admin_user,
                rol='admin',
                empresa='MBOARD',
                telefono='+56 9 1234 5678'
            )
            self.stdout.write(self.style.SUCCESS('Superusuario creado: admin/admin123'))

        # Crear usuarios de ejemplo
        usuarios_data = [
            {'username': 'carlos.martinez', 'first_name': 'Carlos', 'last_name': 'Martínez Silva', 'email': 'carlos@sodimac.cl', 'empresa': 'Sodimac', 'rol': 'operador'},
            {'username': 'ana.garcia', 'first_name': 'Ana', 'last_name': 'García López', 'email': 'ana@dimaplac.cl', 'empresa': 'Dimaplac', 'rol': 'operador'},
            {'username': 'luis.moreno', 'first_name': 'Luis', 'last_name': 'Moreno Torres', 'email': 'luis@sodimac.cl', 'empresa': 'Sodimac', 'rol': 'operador'},
            {'username': 'patricia.gonzalez', 'first_name': 'Patricia', 'last_name': 'González Herrera', 'email': 'patricia@dimaplac.cl', 'empresa': 'Dimaplac', 'rol': 'admin'},
        ]

        for user_data in usuarios_data:
            if not User.objects.filter(username=user_data['username']).exists():
                user = User.objects.create_user(
                    username=user_data['username'],
                    password='password123',
                    first_name=user_data['first_name'],
                    last_name=user_data['last_name'],
                    email=user_data['email']
                )
                UsuarioPerfilOptimizador.objects.create(
                    user=user,
                    rol=user_data['rol'],
                    empresa=user_data['empresa'],
                    telefono=f'+56 9 {random.randint(1000, 9999)} {random.randint(1000, 9999)}'
                )

        # Crear clientes
        clientes_data = [
            {'rut': '15.234.567-8', 'nombre': 'Patricia González Herrera', 'empresa': 'Constructora Patricios', 'telefono': '+56 9 8765 4321', 'email': 'patricia@constructora.cl'},
            {'rut': '18.765.432-1', 'nombre': 'Rodrigo Jiménez Soto', 'empresa': 'Muebles Rodrigo', 'telefono': '+56 9 7654 3210', 'email': 'rodrigo@muebles.cl'},
            {'rut': '12.987.654-3', 'nombre': 'Carmen Morales Espinoza', 'empresa': 'Diseños Carmen', 'telefono': '+56 9 6543 2109', 'email': 'carmen@disenos.cl'},
            {'rut': '16.543.210-9', 'nombre': 'Diego Vargas Mendoza', 'empresa': 'Vargas y Asociados', 'telefono': '+56 9 5432 1098', 'email': 'diego@vargas.cl'},
            {'rut': '13.456.789-0', 'nombre': 'Francisca Ramírez Castro', 'empresa': 'Carpintería Francisca', 'telefono': '+56 9 4321 0987', 'email': 'francisca@carpinteria.cl'},
        ]

        for cliente_data in clientes_data:
            if not Cliente.objects.filter(rut=cliente_data['rut']).exists():
                Cliente.objects.create(**cliente_data)

        # Crear materiales
        materiales_data = [
            {'codigo': 'MEL-001', 'nombre': 'Melamina Grafito 15mm', 'tipo': 'melamina', 'espesor': 15.0, 'ancho': 1830, 'largo': 2500, 'precio_m2': 28500, 'stock': 50, 'proveedor': 'Masisa'},
            {'codigo': 'MEL-002', 'nombre': 'Melamina Nogal 18mm', 'tipo': 'melamina', 'espesor': 18.0, 'ancho': 1830, 'largo': 2500, 'precio_m2': 32000, 'stock': 35, 'proveedor': 'Arauco'},
            {'codigo': 'MEL-003', 'nombre': 'Melamina Blanco 15mm', 'tipo': 'melamina', 'espesor': 15.0, 'ancho': 1830, 'largo': 2500, 'precio_m2': 26500, 'stock': 60, 'proveedor': 'Masisa'},
            {'codigo': 'MDF-001', 'nombre': 'MDF Crudo 18mm', 'tipo': 'mdf', 'espesor': 18.0, 'ancho': 1830, 'largo': 2440, 'precio_m2': 22000, 'stock': 40, 'proveedor': 'Arauco'},
            {'codigo': 'OSB-001', 'nombre': 'OSB Estructural 15mm', 'tipo': 'osb', 'espesor': 15.0, 'ancho': 1220, 'largo': 2440, 'precio_m2': 18500, 'stock': 30, 'proveedor': 'LP'},
        ]

        for material_data in materiales_data:
            if not Material.objects.filter(codigo=material_data['codigo']).exists():
                Material.objects.create(**material_data)

        # Crear tapacantos
        tapacantos_data = [
            {'codigo': 'PVC-001', 'nombre': 'PVC Grafito', 'color': 'Grafito', 'ancho': 19.0, 'espesor': 1.5, 'precio_metro': 650, 'stock_metros': 500, 'proveedor': 'Rehau'},
            {'codigo': 'PVC-002', 'nombre': 'PVC Nogal', 'color': 'Nogal', 'ancho': 22.0, 'espesor': 2.0, 'precio_metro': 750, 'stock_metros': 300, 'proveedor': 'Rehau'},
            {'codigo': 'PVC-003', 'nombre': 'PVC Blanco', 'color': 'Blanco', 'ancho': 19.0, 'espesor': 1.5, 'precio_metro': 620, 'stock_metros': 600, 'proveedor': 'Rehau'},
            {'codigo': 'ABS-001', 'nombre': 'ABS Grafito', 'color': 'Grafito', 'ancho': 23.0, 'espesor': 1.0, 'precio_metro': 850, 'stock_metros': 200, 'proveedor': 'Formica'},
        ]

        for tapacanto_data in tapacantos_data:
            if not Tapacanto.objects.filter(codigo=tapacanto_data['codigo']).exists():
                Tapacanto.objects.create(**tapacanto_data)

        # Crear proyectos
        clientes = list(Cliente.objects.all())
        usuarios = list(User.objects.all())
        estados = ['borrador', 'en_proceso', 'optimizado', 'aprobado', 'produccion', 'completado']
        
        proyectos_data = [
            {'nombre': 'Sistema de Inventario Digital', 'descripcion': 'Optimización de corte para sistema de inventario modular'},
            {'nombre': 'Plataforma E-commerce Muebles', 'descripcion': 'Corte optimizado para plataforma de exhibición'},
            {'nombre': 'App Móvil Gestión Logística', 'descripcion': 'Muebles para aplicación de gestión logística'},
            {'nombre': 'Optimización Costos Producción', 'descripcion': 'Análisis y optimización de costos de materiales'},
            {'nombre': 'Análisis Eficiencia Materiales', 'descripcion': 'Estudio de eficiencia en el uso de materiales'},
        ]

        for i, proyecto_data in enumerate(proyectos_data, 1):
            if not Proyecto.objects.filter(codigo=f'PROJ-{i:03d}').exists():
                Proyecto.objects.create(
                    codigo=f'PROJ-{i:03d}',
                    nombre=proyecto_data['nombre'],
                    cliente=random.choice(clientes),
                    descripcion=proyecto_data['descripcion'],
                    estado=random.choice(estados),
                    fecha_inicio=date(2024, random.randint(1, 12), random.randint(1, 28)),
                    total_materiales=random.randint(1, 5),
                    total_tableros=random.randint(1, 10),
                    total_piezas=random.randint(5, 30),
                    eficiencia_promedio=random.uniform(75, 95),
                    costo_total=random.uniform(500000, 2000000),
                    creado_por=random.choice(usuarios)
                )

        self.stdout.write(self.style.SUCCESS('¡Datos de ejemplo creados exitosamente!'))
        self.stdout.write(self.style.WARNING('Usuarios creados:'))
        self.stdout.write('- admin/admin123 (Superusuario)')
        self.stdout.write('- carlos.martinez/password123')
        self.stdout.write('- ana.garcia/password123')
        self.stdout.write('- luis.moreno/password123')
        self.stdout.write('- patricia.gonzalez/password123')