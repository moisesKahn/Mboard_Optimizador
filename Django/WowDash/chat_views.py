from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.db.models import Q, Max, Count
from django.db import models
from django.utils import timezone
from django.contrib import messages
from core.models import Conversacion, Mensaje, MensajeLeido, UsuarioPerfilOptimizador
from core.auth_utils import get_auth_context
import json
from django.core.paginator import Paginator
from django.urls import reverse


@login_required
def chat_lista(request):
    """Vista principal del chat - lista de conversaciones"""
    ctx = get_auth_context(request)
    base = Conversacion.objects.filter(participantes=request.user)
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        base = base.filter(organizacion_id=ctx.get('organization_id'))
    conversaciones = base.prefetch_related('participantes', 'mensajes').distinct().order_by('-actualizado_en')
    
    # Agregar información adicional a cada conversación
    for conversacion in conversaciones:
        # Importante: calcular nombre_display ANTES de tocar otros atributos para no romper métodos
        nombre_disp = conversacion.nombre_display(request.user)
        no_leidos = conversacion.mensajes_no_leidos(request.user)
        # Asignar alias que el template espera
        conversacion.nombre_display = nombre_disp
        conversacion.mensajes_no_leidos = no_leidos
        # No sobrescribir el método otros_participantes; si se requiere, usar un alias distinto
    
    # Buscar conversaciones
    search = request.GET.get('search', '')
    if search:
        conversaciones = conversaciones.filter(
            Q(nombre__icontains=search) |
            Q(participantes__first_name__icontains=search) |
            Q(participantes__last_name__icontains=search) |
            Q(participantes__username__icontains=search)
        ).distinct()
    
    # Obtener usuarios disponibles para iniciar chat
    usuarios_disponibles = User.objects.filter(is_active=True).exclude(id=request.user.id)
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        usuarios_disponibles = usuarios_disponibles.filter(usuarioperfiloptimizador__organizacion_id=ctx.get('organization_id'))
    
    # Conversación activa (la primera por defecto)
    conversacion_activa = conversaciones.first()
    mensajes = []
    
    if conversacion_activa:
        mensajes = conversacion_activa.mensajes.all().select_related('autor')[:50]
        # Marcar mensajes como leídos
        mensajes_no_leidos = conversacion_activa.mensajes.exclude(autor=request.user).filter(leido=False)
        for mensaje in mensajes_no_leidos:
            MensajeLeido.objects.get_or_create(usuario=request.user, mensaje=mensaje)
            mensaje.leido = True
            mensaje.save(update_fields=['leido'])
    
    context = {
        "title": "Chat",
        "subTitle": "Mensajería",
        "conversaciones": conversaciones,
        "conversacion_actual": conversacion_activa,
        "mensajes": mensajes,
        "usuarios_disponibles": usuarios_disponibles,
        "search": search,
        "usuario_actual": request.user,
    }
    return render(request, "chat_dynamic.html", context)


@login_required
def chat_conversacion(request, conversacion_id):
    """Vista para una conversación específica"""
    ctx = get_auth_context(request)
    base = Conversacion.objects.filter(participantes=request.user)
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        base = base.filter(organizacion_id=ctx.get('organization_id'))
    # Recuperar la conversación dentro del mismo scoping; si no existe, redirigir con aviso
    conversacion = base.filter(id=conversacion_id).first()
    if not conversacion:
        messages.warning(request, 'No tienes acceso a esta conversación o no existe.')
        return redirect('chat')
    
    # Obtener mensajes de la conversación (soportar foco en mensaje específico)
    focus_id = request.GET.get('focus')
    mensajes = []
    if focus_id:
        try:
            foco = conversacion.mensajes.get(id=int(focus_id))
            prevs = list(conversacion.mensajes.filter(id__lte=foco.id).order_by('-id').select_related('autor')[:25])
            nexts = list(conversacion.mensajes.filter(id__gt=foco.id).order_by('id').select_related('autor')[:25])
            prevs.reverse()
            mensajes = prevs + nexts
        except Exception:
            mensajes = list(conversacion.mensajes.all().select_related('autor')[:50])
    else:
        mensajes = conversacion.mensajes.all().select_related('autor')[:50]
    
    # Marcar mensajes como leídos
    mensajes_no_leidos = conversacion.mensajes.exclude(autor=request.user).filter(leido=False)
    for mensaje in mensajes_no_leidos:
        MensajeLeido.objects.get_or_create(usuario=request.user, mensaje=mensaje)
        mensaje.leido = True
        mensaje.save(update_fields=['leido'])
    
    # Obtener todas las conversaciones para la sidebar (respetando el mismo scoping)
    conversaciones = base.prefetch_related('participantes').distinct().order_by('-actualizado_en')
    for c in conversaciones:
        c.nombre_display = c.nombre_display(request.user)
        c.mensajes_no_leidos = c.mensajes_no_leidos(request.user)
    
    # Usuarios disponibles
    usuarios_disponibles = User.objects.filter(
        is_active=True,
        usuarioperfiloptimizador__activo=True
    ).exclude(id=request.user.id).select_related('usuarioperfiloptimizador')
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        usuarios_disponibles = usuarios_disponibles.filter(
            usuarioperfiloptimizador__organizacion_id=ctx.get('organization_id')
        )
    
    context = {
        "title": "Chat",
        "subTitle": "Mensajería",
        "conversaciones": conversaciones,
        "conversacion_actual": conversacion,
        "mensajes": mensajes,
        "usuarios_disponibles": usuarios_disponibles,
        "usuario_actual": request.user,
        "focus_id": int(focus_id) if focus_id else None,
    }
    return render(request, "chat_dynamic.html", context)


@login_required
def enviar_mensaje(request):
    """API para enviar un mensaje"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            conversacion_id = data.get('conversacion_id')
            contenido = data.get('contenido', '').strip()
            
            if not contenido:
                return JsonResponse({'success': False, 'error': 'El contenido no puede estar vacío'})
            
            ctx = get_auth_context(request)
            base = Conversacion.objects.filter(participantes=request.user)
            if not (ctx.get('organization_is_general') or ctx.get('is_support')):
                base = base.filter(organizacion_id=ctx.get('organization_id'))
            conversacion = get_object_or_404(base, id=conversacion_id)
            
            # Crear el mensaje
            mensaje = Mensaje.objects.create(
                conversacion=conversacion,
                autor=request.user,
                contenido=contenido
            )
            
            # Marcar como leído para el autor
            MensajeLeido.objects.create(usuario=request.user, mensaje=mensaje)
            
            return JsonResponse({
                'success': True,
                'mensaje': {
                    'id': mensaje.id,
                    'contenido': mensaje.contenido,
                    'autor': mensaje.autor.get_full_name() or mensaje.autor.username,
                    'autor_id': mensaje.autor.id,
                    'enviado_en': mensaje.enviado_en.strftime('%H:%M'),
                    'fecha_completa': mensaje.enviado_en.strftime('%d/%m/%Y %H:%M')
                }
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required
def crear_conversacion(request):
    """API para crear una nueva conversación"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            participante_id = data.get('participante_id')
            primer_mensaje = data.get('mensaje', '').strip()
            
            if not participante_id:
                return JsonResponse({'success': False, 'error': 'Debe seleccionar un participante'})
            
            ctx = get_auth_context(request)
            base_users = User.objects.filter(is_active=True)
            if not (ctx.get('organization_is_general') or ctx.get('is_support')):
                base_users = base_users.filter(usuarioperfiloptimizador__organizacion_id=ctx.get('organization_id'))
            participante = get_object_or_404(base_users, id=participante_id)
            
            # Verificar si ya existe una conversación entre estos usuarios
            conversacion_existente = Conversacion.objects.filter(
                participantes__in=[request.user, participante],
                es_grupal=False
            ).annotate(
                num_participantes=models.Count('participantes')
            ).filter(num_participantes=2).first()
            
            if conversacion_existente:
                conversacion = conversacion_existente
            else:
                # Crear nueva conversación
                conversacion = Conversacion.objects.create(
                    creado_por=request.user,
                    es_grupal=False,
                    organizacion=getattr(request.user.usuarioperfiloptimizador, 'organizacion', None)
                )
                conversacion.participantes.add(request.user, participante)
            
            # Si hay un primer mensaje, enviarlo
            if primer_mensaje:
                mensaje = Mensaje.objects.create(
                    conversacion=conversacion,
                    autor=request.user,
                    contenido=primer_mensaje
                )
                MensajeLeido.objects.create(usuario=request.user, mensaje=mensaje)
            
            return JsonResponse({
                'success': True,
                'conversacion_id': conversacion.id,
                'redirect_url': reverse('chat_conversacion', args=[conversacion.id])
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})


@login_required
def obtener_mensajes(request, conversacion_id):
    """API para obtener mensajes más recientes"""
    ctx = get_auth_context(request)
    base = Conversacion.objects.filter(participantes=request.user)
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        base = base.filter(organizacion_id=ctx.get('organization_id'))
    conversacion = get_object_or_404(base, id=conversacion_id)
    
    # Obtener el ID del último mensaje recibido
    try:
        ultimo_mensaje_id = int(request.GET.get('ultimo_id', 0) or 0)
    except (TypeError, ValueError):
        ultimo_mensaje_id = 0
    
    # Obtener mensajes más recientes
    mensajes = conversacion.mensajes.filter(
        id__gt=ultimo_mensaje_id
    ).select_related('autor')[:20]
    
    # Marcar mensajes como leídos
    mensajes_no_leidos = mensajes.exclude(autor=request.user).filter(leido=False)
    for mensaje in mensajes_no_leidos:
        MensajeLeido.objects.get_or_create(usuario=request.user, mensaje=mensaje)
        mensaje.leido = True
        mensaje.save(update_fields=['leido'])
    
    mensajes_data = []
    for mensaje in mensajes:
        mensajes_data.append({
            'id': mensaje.id,
            'contenido': mensaje.contenido,
            'autor': mensaje.autor.get_full_name() or mensaje.autor.username,
            'autor_id': mensaje.autor.id,
            'enviado_en': mensaje.enviado_en.strftime('%H:%M'),
            'fecha_completa': mensaje.enviado_en.strftime('%d/%m/%Y %H:%M'),
            'es_mio': mensaje.autor == request.user
        })
    
    return JsonResponse({
        'success': True,
        'mensajes': mensajes_data
    })


@login_required
def chat_perfil(request):
    """Vista del perfil de chat"""
    usuario = request.user
    try:
        perfil = usuario.usuarioperfiloptimizador
    except UsuarioPerfilOptimizador.DoesNotExist:
        perfil = None
    
    context = {
        "title": "Perfil de Chat",
        "subTitle": "Configuración",
        "usuario": usuario,
        "perfil": perfil,
    }
    return render(request, "chatProfile.html", context)


@login_required
def buscar_usuarios(request):
    """API para buscar usuarios disponibles para chat"""
    query = request.GET.get('q', '').strip()
    
    if len(query) < 2:
        return JsonResponse({'usuarios': []})
    
    ctx = get_auth_context(request)
    usuarios = User.objects.filter(
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(username__icontains=query) |
        Q(email__icontains=query),
        is_active=True,
        usuarioperfiloptimizador__activo=True
    ).exclude(id=request.user.id).select_related('usuarioperfiloptimizador')
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        usuarios = usuarios.filter(usuarioperfiloptimizador__organizacion_id=ctx.get('organization_id'))
    usuarios = usuarios[:10]
    
    usuarios_data = []
    for usuario in usuarios:
        usuarios_data.append({
            'id': usuario.id,
            'nombre': usuario.get_full_name() or usuario.username,
            'username': usuario.username,
            'email': usuario.email,
            'organizacion': usuario.usuarioperfiloptimizador.organizacion.nombre if hasattr(usuario, 'usuarioperfiloptimizador') and usuario.usuarioperfiloptimizador.organizacion else 'Sin organización'
        })
    
    return JsonResponse({'usuarios': usuarios_data})


@login_required
def buscar_mensajes(request):
    """API para búsqueda avanzada de mensajes por contenido en todas las conversaciones del usuario."""
    q = (request.GET.get('q') or '').strip()
    if len(q) < 2:
        return JsonResponse({'resultados': []})

    ctx = get_auth_context(request)
    convs = Conversacion.objects.filter(participantes=request.user)
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        convs = convs.filter(organizacion_id=ctx.get('organization_id'))

    mensajes = Mensaje.objects.filter(
        conversacion__in=convs,
        contenido__icontains=q
    ).select_related('conversacion', 'autor').order_by('-id')[:30]

    resultados = []
    for m in mensajes:
        try:
            conv = m.conversacion
            resultados.append({
                'conversacion_id': conv.id,
                'conversacion_nombre': conv.nombre_display(request.user),
                'mensaje_id': m.id,
                'autor': m.autor.get_full_name() or m.autor.username,
                'hora': m.enviado_en.strftime('%d/%m %H:%M'),
                'snippet': (m.contenido[:140] + ('…' if len(m.contenido) > 140 else ''))
            })
        except Exception:
            continue

    return JsonResponse({'resultados': resultados})


@login_required
def unread_summary(request):
    """API para obtener resumen de mensajes no leídos del usuario actual.
    Devuelve el total y el detalle por conversación para poder mostrar badges/notificaciones.
    """
    user = request.user
    ctx = get_auth_context(request)
    convs = Conversacion.objects.filter(participantes=user)
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        convs = convs.filter(organizacion_id=ctx.get('organization_id'))

    # Mensajes no leídos donde el autor no es el usuario actual
    qs = Mensaje.objects.filter(conversacion__in=convs, leido=False).exclude(autor=user)

    total_unread = qs.count()
    base = qs.values('conversacion_id').annotate(unread=models.Count('id'), ultimo_id=models.Max('id')).order_by('-ultimo_id')
    por_conversacion = []
    # Adjuntar nombres de conversación de forma segura (normalmente son pocos)
    for item in base:
        conv_id = item['conversacion_id']
        try:
            conv = Conversacion.objects.get(id=conv_id)
            nombre = conv.nombre_display(request.user)
        except Exception:
            nombre = f"Conversación {conv_id}"
        por_conversacion.append({
            'conversacion_id': conv_id,
            'unread': item['unread'],
            'ultimo_id': item['ultimo_id'],
            'nombre': nombre,
        })

    return JsonResponse({
        'success': True,
        'total_unread': total_unread,
        'conversaciones': por_conversacion,
    })