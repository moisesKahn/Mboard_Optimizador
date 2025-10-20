from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q
from django.contrib.auth.models import User
from core.models import Cliente, Proyecto, UsuarioPerfilOptimizador, Organizacion
import json

@login_required
def global_search(request):
    """Búsqueda global en la aplicación"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'results': []})
    
    results = []
    
    # Buscar en Proyectos
    proyectos = Proyecto.objects.filter(
        Q(codigo__icontains=query) | 
        Q(nombre__icontains=query)
    )[:5]
    
    for proyecto in proyectos:
        # Determinar qué campo coincidió para la búsqueda
        search_term = proyecto.codigo if query.lower() in proyecto.codigo.lower() else proyecto.nombre
        results.append({
            'type': 'proyecto',
            'title': f"Proyecto: {proyecto.codigo}",
            'subtitle': proyecto.nombre,
            'url': f'/proyectos/?search={search_term}',
            'icon': 'solar:document-bold'
        })
    
    # Buscar en Clientes
    clientes = Cliente.objects.filter(
        Q(rut__icontains=query) |
        Q(nombre__icontains=query) |
        Q(email__icontains=query)
    )[:5]
    
    for cliente in clientes:
        # Determinar qué campo coincidió para la búsqueda
        if query.lower() in cliente.rut.lower():
            search_term = cliente.rut
        elif query.lower() in cliente.nombre.lower():
            search_term = cliente.nombre
        else:
            search_term = cliente.email or cliente.nombre
            
        results.append({
            'type': 'cliente',
            'title': f"Cliente: {cliente.rut}",
            'subtitle': cliente.nombre,
            'url': f'/clientes/?search={search_term}',
            'icon': 'solar:user-bold'
        })
    
    # Buscar en Usuarios
    usuarios = User.objects.filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query)
    ).select_related('usuarioperfiloptimizador')[:5]
    
    for usuario in usuarios:
        # Determinar qué campo coincidió para la búsqueda
        if query.lower() in usuario.username.lower():
            search_term = usuario.username
        elif usuario.first_name and query.lower() in usuario.first_name.lower():
            search_term = usuario.first_name
        elif usuario.last_name and query.lower() in usuario.last_name.lower():
            search_term = usuario.last_name
        elif usuario.email and query.lower() in usuario.email.lower():
            search_term = usuario.email
        else:
            search_term = usuario.username
            
        results.append({
            'type': 'usuario',
            'title': f"Usuario: {usuario.username}",
            'subtitle': usuario.get_full_name() or usuario.email,
            'url': f'/users/users-list/?search={search_term}',
            'icon': 'solar:users-group-rounded-bold'
        })
    
    # Buscar en Organizaciones
    organizaciones = Organizacion.objects.filter(
        Q(codigo__icontains=query) |
        Q(nombre__icontains=query)
    )[:5]
    
    for org in organizaciones:
        # Determinar qué campo coincidió para la búsqueda
        search_term = org.codigo if query.lower() in org.codigo.lower() else org.nombre
        results.append({
            'type': 'organizacion',
            'title': f"Organización: {org.codigo}",
            'subtitle': org.nombre,
            'url': f'/organizaciones/?search={search_term}',
            'icon': 'solar:buildings-bold'
        })
    
    return JsonResponse({'results': results})