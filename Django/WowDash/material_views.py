from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest, FileResponse, Http404, HttpResponse
from django.views.decorators.http import require_POST
import csv
import io
import os
from django.db.models import Q
from django.template.loader import render_to_string
from core.models import Material, Tapacanto, UsuarioPerfilOptimizador
from core.forms import MaterialForm, TapacantoForm
from core.auth_utils import get_auth_context, is_support, is_org_admin, is_agent, is_subordinador
from django.conf import settings

def _deny_if_readonly_role(request):
    """Devuelve (denied:bool, response) si el rol no puede escribir Materiales/Tapacantos"""
    ctx = get_auth_context(request)
    if is_support(ctx) or is_org_admin(ctx):
        return False, None
    # Agente/Subordinador: solo lectura
    if is_agent(ctx) or is_subordinador(ctx):
        return True, JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)
    return True, JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)

def get_user_organization(request):
    """
    Helper function para obtener la organización del usuario actual.
    Para Super Admins, retorna None (acceso a todo).
    Para otros roles, retorna la organización específica.
    Retorna (organizacion, None) si todo está bien, o (None, redirect_response) si hay problema.
    """
    if not request.user.is_authenticated:
        return None, redirect('authentication_signin')
    
    try:
        perfil_usuario = request.user.usuarioperfiloptimizador
        
        # Super Admins tienen acceso a todas las organizaciones
        if perfil_usuario.rol == 'super_admin':
            return None, None  # None significa "todas las organizaciones"
        
        # Para otros roles, necesitan organización asignada
        organizacion_usuario = perfil_usuario.organizacion
        
    except UsuarioPerfilOptimizador.DoesNotExist:
        messages.error(request, 'No tienes un perfil de usuario válido. Contacta al administrador del sistema.')
        return None, redirect('index')
    
    if not organizacion_usuario:
        messages.error(request, 'No tienes una organización asignada. Contacta al administrador para que te asigne a una organización.')
        return None, redirect('index')
    
    return organizacion_usuario, None

@login_required
def tableros_list(request):
    """Lista de tableros (materiales)"""
    # Obtener organización del usuario
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return error_response
    
    # Filtros de búsqueda
    search = request.GET.get('search', '')
    tipo_filter = request.GET.get('tipo', '')
    # Paginación
    try:
        page_size = max(1, min(100, int(request.GET.get('page_size', '10'))))
    except ValueError:
        page_size = 10
    try:
        page = max(1, int(request.GET.get('page', '1')))
    except ValueError:
        page = 1
    
    # Query base - Super Admins ven todos los materiales, otros solo de su organización
    if organizacion_usuario is None:  # Super Admin
        materiales = Material.objects.filter(activo=True)
    else:  # Usuarios con organización específica
        materiales = Material.objects.filter(activo=True, organizacion=organizacion_usuario)
    
    # Aplicar filtros
    if search:
        materiales = materiales.filter(
            Q(codigo__icontains=search) | 
            Q(nombre__icontains=search) |
            Q(proveedor__icontains=search)
        )
    
    if tipo_filter:
        materiales = materiales.filter(tipo=tipo_filter)
    
    # Orden y paginación
    materiales = materiales.order_by('-id')
    total = materiales.count()
    start = (page - 1) * page_size
    end = start + page_size
    materiales = materiales[start:end]
    total_pages = (total + page_size - 1) // page_size
    # Obtener tipos únicos para el filtro
    tipos_materiales = Material.TIPOS_MATERIAL

    context = {
        "title": "Lista de Tableros",
        "subTitle": "Tableros",
        "materiales": materiales,
        "tipos_materiales": tipos_materiales,
        "search": search,
        "tipo_filter": tipo_filter,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "page_sizes": [10,20,30,50,100],
    }
    return render(request, 'materials/tableros_list.html', context)

@login_required
def add_tablero(request):
    """Agregar nuevo tablero"""
    denied, resp = _deny_if_readonly_role(request)
    if denied:
        return resp
    # Obtener organización del usuario
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return error_response

    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            material = form.save(commit=False)
            # Super Admin asigna a primera org por simplicidad
            if organizacion_usuario is None:
                from core.models import Organizacion
                primera_org = Organizacion.objects.first()
                material.organizacion = primera_org
                messages.info(request, f'Material asignado a organización: {primera_org.nombre}')
            else:
                material.organizacion = organizacion_usuario
            material.save()
            messages.success(request, 'Material agregado exitosamente.')
            return redirect('tableros')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = MaterialForm()

    context = {
        "title": "Agregar Tablero",
        "subTitle": "Nuevo Tablero",
        "form": form
    }
    return render(request, 'materials/add_tablero.html', context)

@login_required
def tapacantos_list(request):
    """Lista de tapacantos"""
    # Obtener organización del usuario
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return error_response
    
    # Filtros de búsqueda
    search = request.GET.get('search', '')
    # Paginación
    try:
        page_size = max(1, min(100, int(request.GET.get('page_size', '10'))))
    except ValueError:
        page_size = 10
    try:
        page = max(1, int(request.GET.get('page', '1')))
    except ValueError:
        page = 1
    
    # Query base - Super Admins ven todos los tapacantos, otros solo de su organización
    if organizacion_usuario is None:  # Super Admin
        tapacantos = Tapacanto.objects.filter(activo=True)
    else:  # Usuarios con organización específica
        tapacantos = Tapacanto.objects.filter(activo=True, organizacion=organizacion_usuario)
    
    # Aplicar filtros
    if search:
        tapacantos = tapacantos.filter(
            Q(codigo__icontains=search) | 
            Q(nombre__icontains=search) |
            Q(color__icontains=search) |
            Q(proveedor__icontains=search)
        )
    
    # Orden y paginación
    tapacantos = tapacantos.order_by('-id')
    total = tapacantos.count()
    start = (page - 1) * page_size
    end = start + page_size
    tapacantos = tapacantos[start:end]
    total_pages = (total + page_size - 1) // page_size

    context = {
        "title": "Lista de Tapacantos", 
        "subTitle": "Tapacantos",
        "tapacantos": tapacantos,
        "search": search,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
        "page_sizes": [10,20,30,50,100],
    }
    return render(request, 'materials/tapacantos_list.html', context)

@login_required
def add_tapacanto(request):
    """Agregar nuevo tapacanto"""
    denied, resp = _deny_if_readonly_role(request)
    if denied:
        return resp
    # Obtener organización del usuario
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return error_response
    
    if request.method == 'POST':
        form = TapacantoForm(request.POST)
        if form.is_valid():
            tapacanto = form.save(commit=False)
            
            # Super Admins pueden crear tapacantos para cualquier organización
            # Por ahora, asignar a la primera organización disponible
            if organizacion_usuario is None:  # Super Admin
                from core.models import Organizacion
                primera_org = Organizacion.objects.first()
                tapacanto.organizacion = primera_org
                messages.info(request, f'Tapacanto asignado a organización: {primera_org.nombre}')
            else:
                tapacanto.organizacion = organizacion_usuario
                
            tapacanto.save()
            messages.success(request, 'Tapacanto agregado exitosamente.')
            return redirect('tapacantos')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = TapacantoForm()
    
    context = {
        "title": "Agregar Tapacanto",
        "subTitle": "Nuevo Tapacanto",
        "form": form
    }
    return render(request, 'materials/add_tapacanto.html', context)

@login_required
def edit_tablero(request, tablero_id):
    """Editar tablero existente"""
    denied, resp = _deny_if_readonly_role(request)
    if denied:
        return resp
    # Obtener organización del usuario
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return error_response
    
    # Super Admins pueden editar cualquier material, otros solo de su organización
    if organizacion_usuario is None:  # Super Admin
        material = get_object_or_404(Material, pk=tablero_id)
    else:
        material = get_object_or_404(Material, pk=tablero_id, organizacion=organizacion_usuario)
    
    if request.method == 'POST':
        form = MaterialForm(request.POST, instance=material)
        if form.is_valid():
            form.save()
            messages.success(request, 'Material actualizado exitosamente.')
            return redirect('tableros')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = MaterialForm(instance=material)
    
    context = {
        "title": "Editar Tablero",
        "subTitle": "Modificar Tablero",
        "form": form,
        "material": material
    }
    return render(request, 'materials/edit_tablero.html', context)

@login_required
def edit_tapacanto(request, tapacanto_id):
    """Editar tapacanto existente"""
    denied, resp = _deny_if_readonly_role(request)
    if denied:
        return resp
    # Obtener organización del usuario
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return error_response
    
    # Super Admins pueden editar cualquier tapacanto, otros solo de su organización
    if organizacion_usuario is None:  # Super Admin
        tapacanto = get_object_or_404(Tapacanto, pk=tapacanto_id)
    else:
        tapacanto = get_object_or_404(Tapacanto, pk=tapacanto_id, organizacion=organizacion_usuario)
    
    if request.method == 'POST':
        form = TapacantoForm(request.POST, instance=tapacanto)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tapacanto actualizado exitosamente.')
            return redirect('tapacantos')
        else:
            messages.error(request, 'Por favor corrige los errores del formulario.')
    else:
        form = TapacantoForm(instance=tapacanto)
    
    context = {
        "title": "Editar Tapacanto", 
        "subTitle": "Modificar Tapacanto",
        "form": form,
        "tapacanto": tapacanto
    }
    return render(request, 'materials/edit_tapacanto.html', context)

# APIs para manejo AJAX
@login_required
def delete_tablero(request, tablero_id):
    """Eliminar (desactivar) tablero vía AJAX"""
    if request.method == 'POST':
        try:
            denied, resp = _deny_if_readonly_role(request)
            if denied:
                return resp
            # Obtener organización del usuario
            organizacion_usuario, error_response = get_user_organization(request)
            if error_response:
                return JsonResponse({'success': False, 'message': 'No tienes una organización asignada'})
            
            # Super Admins pueden eliminar cualquier material, otros solo de su organización
            if organizacion_usuario is None:  # Super Admin
                material = get_object_or_404(Material, pk=tablero_id)
            else:
                material = get_object_or_404(Material, pk=tablero_id, organizacion=organizacion_usuario)
            material.activo = False
            material.save()
            return JsonResponse({
                'success': True,
                'message': 'Material eliminado exitosamente.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al eliminar material: {str(e)}'
            })
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
def delete_tapacanto(request, tapacanto_id):
    """Eliminar (desactivar) tapacanto vía AJAX"""
    if request.method == 'POST':
        try:
            denied, resp = _deny_if_readonly_role(request)
            if denied:
                return resp
            # Obtener organización del usuario
            organizacion_usuario, error_response = get_user_organization(request)
            if error_response:
                return JsonResponse({'success': False, 'message': 'No tienes una organización asignada'})
            
            # Super Admins pueden eliminar cualquier tapacanto, otros solo de su organización
            if organizacion_usuario is None:  # Super Admin
                tapacanto = get_object_or_404(Tapacanto, pk=tapacanto_id)
            else:
                tapacanto = get_object_or_404(Tapacanto, pk=tapacanto_id, organizacion=organizacion_usuario)
            tapacanto.activo = False
            tapacanto.save()
            return JsonResponse({
                'success': True,
                'message': 'Tapacanto eliminado exitosamente.'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error al eliminar tapacanto: {str(e)}'
            })
    return JsonResponse({'success': False, 'message': 'Método no permitido'})

@login_required
def tableros_search_ajax(request):
    """Búsqueda AJAX para tableros en tiempo real"""
    search = request.GET.get('search', '')
    tipo_filter = request.GET.get('tipo', '')
    
    # Obtener organización del usuario
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return JsonResponse({'error': 'Error de organización'})
    
    # Query base - Super Admins ven todos los materiales, otros solo de su organización
    if organizacion_usuario is None:  # Super Admin
        materiales = Material.objects.filter(activo=True)
    else:  # Usuarios con organización específica
        materiales = Material.objects.filter(activo=True, organizacion=organizacion_usuario)
    
    # Aplicar filtros
    if search:
        materiales = materiales.filter(
            Q(codigo__icontains=search) | 
            Q(nombre__icontains=search) |
            Q(proveedor__icontains=search)
        )
    
    if tipo_filter:
        materiales = materiales.filter(tipo=tipo_filter)
    
    # Obtener tipos únicos para el filtro
    tipos_materiales = Material.TIPOS_MATERIAL
    
    # Renderizar la tabla
    html = render_to_string('materials/tableros_table_partial.html', {
        'materiales': materiales,
        'tipos_materiales': tipos_materiales,
        'search': search,
        'tipo_filter': tipo_filter
    })
    
    return JsonResponse({
        'html': html,
        'count': materiales.count()
    })

@login_required
def tapacantos_search_ajax(request):
    """Búsqueda AJAX para tapacantos en tiempo real"""
    search = request.GET.get('search', '')
    
    # Obtener organización del usuario
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return JsonResponse({'error': 'Error de organización'})
    
    # Query base - Super Admins ven todos los tapacantos, otros solo de su organización
    if organizacion_usuario is None:  # Super Admin
        tapacantos = Tapacanto.objects.filter(activo=True)
    else:  # Usuarios con organización específica
        tapacantos = Tapacanto.objects.filter(activo=True, organizacion=organizacion_usuario)
    
    # Aplicar filtros
    if search:
        tapacantos = tapacantos.filter(
            Q(codigo__icontains=search) | 
            Q(nombre__icontains=search) |
            Q(color__icontains=search) |
            Q(proveedor__icontains=search)
        )
    
    # Renderizar la tabla
    html = render_to_string('materials/tapacantos_table_partial.html', {
        'tapacantos': tapacantos,
        'search': search
    })
    
    return JsonResponse({
        'html': html,
        'count': tapacantos.count()
    })

@login_required
def descargar_plantilla_tableros(request):
    """Descarga el CSV de plantilla para importar Tableros."""
    ruta = settings.BASE_DIR / 'sample_data' / 'materiales_template.csv'
    if not os.path.exists(ruta):
        raise Http404('Plantilla de tableros no encontrada')
    # FileResponse maneja lectura eficiente y cabeceras adecuadas
    response = FileResponse(open(ruta, 'rb'), content_type='text/csv')
    response["Content-Disposition"] = 'attachment; filename="plantilla_tableros.csv"'
    return response

@login_required
def descargar_plantilla_tapacantos(request):
    """Descarga el CSV de plantilla para importar Tapacantos."""
    ruta = settings.BASE_DIR / 'sample_data' / 'tapacantos_template.csv'
    if not os.path.exists(ruta):
        raise Http404('Plantilla de tapacantos no encontrada')
    response = FileResponse(open(ruta, 'rb'), content_type='text/csv')
    response["Content-Disposition"] = 'attachment; filename="plantilla_tapacantos.csv"'
    return response

@login_required
@require_POST
def importar_tableros_csv(request):
    """Importa tableros (Material) desde CSV subido (texto en request.body)"""
    denied, resp = _deny_if_readonly_role(request)
    if denied:
        return resp
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return JsonResponse({'success': False, 'message': 'Organización inválida'})
    try:
        # Determinar organización destino
        if organizacion_usuario is None:
            from core.models import Organizacion
            org_target = Organizacion.objects.first()
        else:
            org_target = organizacion_usuario

        # Modo de importación: append (por defecto) o replace
        mode = (request.GET.get('mode') or 'append').lower()
        if mode not in ('append', 'replace'):
            mode = 'append'

        payload = request.body.decode('utf-8', errors='ignore')
        # Detectar delimitador automáticamente para soportar "," y ";"
        sample = payload[:1024]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[',',';','\t'])
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ','
        f = io.StringIO(payload)
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = [c.lower() for c in (reader.fieldnames or [])]
        # Aceptar alias: espesor/espesor_mm, ancho/ancho_mm, largo/largo_mm
        def has_any(*names):
            return any(n in fieldnames for n in names)
        if not (has_any('codigo') and has_any('nombre') and has_any('tipo') and has_any('espesor_mm','espesor') and has_any('ancho_mm','ancho') and has_any('largo_mm','largo')):
            return JsonResponse({'success': False, 'message': 'Columnas requeridas faltantes'}, status=400)
        # Si es reemplazo, desactivar todos los materiales actuales del org
        if mode == 'replace':
            Material.objects.filter(organizacion=org_target, activo=True).update(activo=False)
        creados = 0; actualizados = 0; errores = []
        for i, row in enumerate(reader, start=2):
            try:
                codigo = row.get('codigo') or row.get('CODIGO')
                nombre = row.get('nombre') or row.get('NOMBRE')
                tipo = (row.get('tipo') or '').lower()
                espesor = float(row.get('espesor_mm') or row.get('espesor') or 0)
                a = float((row.get('ancho_mm') or row.get('ancho') or 0) or 0)
                b = float((row.get('largo_mm') or row.get('largo') or 0) or 0)
                mayor, menor = (max(a,b), min(a,b))
                if menor <= 0:
                    raise ValueError('Medidas inválidas')
                if mayor != a:
                    raise ValueError(f'El ancho debe ser la medida mayor (línea {i})')
                precio_m2 = row.get('precio_m2')
                precio_tablero = row.get('precio_tablero')
                if precio_m2:
                    precio_m2 = float(precio_m2)
                elif precio_tablero:
                    area = (mayor*menor)/1_000_000
                    precio_m2 = (float(precio_tablero)/area) if area>0 else 0
                else:
                    precio_m2 = 0
                stock = int(row.get('stock') or 0)
                defaults = dict(nombre=nombre, tipo=tipo, espesor=espesor, ancho=mayor, largo=menor, precio_m2=precio_m2, stock=stock, activo=True)
                mat, created = Material.objects.update_or_create(codigo=codigo, organizacion=org_target, defaults=defaults)
                if created: creados += 1
                else: actualizados += 1
            except Exception as e:
                errores.append(f'Línea {i}: {e}')
        return JsonResponse({'success': len(errores)==0, 'creados': creados, 'actualizados': actualizados, 'errores': errores, 'mode': mode})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
@require_POST
def importar_tapacantos_csv(request):
    """Importa tapacantos desde CSV subido"""
    organizacion_usuario, error_response = get_user_organization(request)
    if error_response:
        return JsonResponse({'success': False, 'message': 'Organización inválida'})
    try:
        # Determinar organización destino
        if organizacion_usuario is None:
            from core.models import Organizacion
            org_target = Organizacion.objects.first()
        else:
            org_target = organizacion_usuario

        # Modo de importación: append o replace
        mode = (request.GET.get('mode') or 'append').lower()
        if mode not in ('append', 'replace'):
            mode = 'append'

        payload = request.body.decode('utf-8', errors='ignore')
        sample = payload[:1024]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=[',',';','\t'])
            delimiter = dialect.delimiter
        except Exception:
            delimiter = ','
        f = io.StringIO(payload)
        reader = csv.DictReader(f, delimiter=delimiter)
        fieldnames = [c.lower() for c in (reader.fieldnames or [])]
        def has_any(*names):
            return any(n in fieldnames for n in names)
        if not (has_any('codigo') and has_any('nombre') and has_any('color') and has_any('ancho_mm','ancho') and has_any('espesor_mm','espesor') and has_any('valor_por_metro','precio_metro')):
            return JsonResponse({'success': False, 'message': 'Columnas requeridas faltantes'}, status=400)
        # Si es replace, desactivar los existentes del org
        if mode == 'replace':
            Tapacanto.objects.filter(organizacion=org_target, activo=True).update(activo=False)
        creados = 0; actualizados = 0; errores = []
        for i, row in enumerate(reader, start=2):
            try:
                codigo = row.get('codigo')
                nombre = row.get('nombre')
                color = row.get('color')
                ancho = float(row.get('ancho_mm') or row.get('ancho') or 0)
                espesor = float(row.get('espesor_mm') or row.get('espesor') or 0)
                valor = float(row.get('valor_por_metro') or row.get('precio_metro') or 0)
                stock_metros = float(row.get('stock_metros') or 0)
                defaults = dict(nombre=nombre, color=color, ancho=ancho, espesor=espesor, precio_metro=valor, stock_metros=stock_metros, activo=True)
                tap, created = Tapacanto.objects.update_or_create(codigo=codigo, organizacion=org_target, defaults=defaults)
                if created: creados += 1
                else: actualizados += 1
            except Exception as e:
                errores.append(f'Línea {i}: {e}')
        return JsonResponse({'success': len(errores)==0, 'creados': creados, 'actualizados': actualizados, 'errores': errores, 'mode': mode})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=400)

@login_required
def descargar_plantilla_tableros_excel(request):
    """Descarga una variante separada por punto y coma para Excel en español."""
    ruta = settings.BASE_DIR / 'sample_data' / 'materiales_template.csv'
    if not os.path.exists(ruta):
        raise Http404('Plantilla de tableros no encontrada')
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    # Instrucción para Excel y reemplazo de delimitador
    contenido = 'sep=;\n' + contenido.replace(',', ';')
    response = HttpResponse(contenido, content_type='text/csv; charset=utf-8')
    response["Content-Disposition"] = 'attachment; filename="plantilla_tableros_excel.csv"'
    return response

@login_required
def descargar_plantilla_tapacantos_excel(request):
    """Variante separada por punto y coma para Excel en español."""
    ruta = settings.BASE_DIR / 'sample_data' / 'tapacantos_template.csv'
    if not os.path.exists(ruta):
        raise Http404('Plantilla de tapacantos no encontrada')
    with open(ruta, 'r', encoding='utf-8') as f:
        contenido = f.read()
    contenido = 'sep=;\n' + contenido.replace(',', ';')
    response = HttpResponse(contenido, content_type='text/csv; charset=utf-8')
    response["Content-Disposition"] = 'attachment; filename="plantilla_tapacantos_excel.csv"'
    return response