# Generated manually to update user roles
from django.db import migrations

def update_roles_forward(apps, schema_editor):
    """Actualizar roles antiguos a nuevos roles"""
    UsuarioPerfilOptimizador = apps.get_model('core', 'UsuarioPerfilOptimizador')
    
    # Mapeo de roles antiguos a nuevos
    role_mapping = {
        'admin': 'org_admin',        # Administradores regulares → Admins de organización
        'operador': 'agente',        # Operadores → Agentes
        'cliente': 'agente',         # Clientes (que usaban sistema) → Agentes
        'visualizador': 'agente',    # Visualizadores → Agentes
        'super_admin': 'super_admin' # Super admins mantienen su rol
    }
    
    usuarios_actualizados = 0
    
    for usuario in UsuarioPerfilOptimizador.objects.all():
        if usuario.rol in role_mapping:
            nuevo_rol = role_mapping[usuario.rol]
            if usuario.rol != nuevo_rol:  # Solo actualizar si cambió
                print(f"Actualizando {usuario.user.username}: {usuario.rol} → {nuevo_rol}")
                usuario.rol = nuevo_rol
                usuario.save()
                usuarios_actualizados += 1
    
    print(f"✅ Actualizados {usuarios_actualizados} usuarios")

def update_roles_backward(apps, schema_editor):
    """Reversar cambios de roles (para rollback)"""
    UsuarioPerfilOptimizador = apps.get_model('core', 'UsuarioPerfilOptimizador')
    
    # Mapeo inverso para rollback
    reverse_mapping = {
        'super_admin': 'admin',
        'org_admin': 'admin', 
        'agente': 'operador'
    }
    
    for usuario in UsuarioPerfilOptimizador.objects.all():
        if usuario.rol in reverse_mapping:
            usuario.rol = reverse_mapping[usuario.rol]
            usuario.save()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_add_organizacion_to_materials'),
    ]

    operations = [
        migrations.RunPython(update_roles_forward, update_roles_backward),
    ]