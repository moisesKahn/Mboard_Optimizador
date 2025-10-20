from django.views.decorators.http import require_POST
from django.contrib.auth import authenticate
from django.http import JsonResponse, HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from django.db.models import Count
from core.models import UsuarioPerfilOptimizador, Cliente, Proyecto, AuditLog, OptimizationRun
from core.auth_utils import jwt_encode, get_auth_context


def _claims_for_user(user: User):
    perfil = None
    org_id = None
    org_general = False
    role = None
    try:
        perfil = user.usuarioperfiloptimizador
        if perfil and perfil.organizacion:
            org_id = perfil.organizacion.id
            org_general = bool(perfil.organizacion.is_general)
        role = perfil.rol
    except UsuarioPerfilOptimizador.DoesNotExist:
        pass
    return {
        'user_id': user.id,
        'username': user.username,
        'organization_id': org_id,
        'organization_is_general': org_general,
        'role': role,
    }


@csrf_exempt
@require_POST
def auth_login(request: HttpRequest):
    try:
        import json
        data = json.loads(request.body or '{}')
        username = data.get('username')
        password = data.get('password')
        if not username or not password:
            return JsonResponse({'success': False, 'message': 'Credenciales requeridas'}, status=400)
        user = authenticate(request, username=username, password=password)
        if not user:
            return JsonResponse({'success': False, 'message': 'Usuario o contraseña inválidos'}, status=401)
        claims = _claims_for_user(user)
        token = jwt_encode(claims)
        # Auditoría LOGIN
        try:
            AuditLog.objects.create(
                actor=user,
                organizacion=getattr(user.usuarioperfiloptimizador, 'organizacion', None),
                verb='LOGIN',
                target_model='User',
                target_id=str(user.id),
                target_repr=user.username,
                changes=None,
            )
        except Exception:
            pass
        return JsonResponse({'success': True, 'token': token, 'claims': claims})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def _scope_queryset_by_org(qs, ctx):
    # Soporte/Org General ve todo
    if ctx.get('organization_is_general') or ctx.get('is_support'):
        return qs
    org_id = ctx.get('organization_id')
    if hasattr(qs.model, 'organizacion_id'):
        return qs.filter(organizacion_id=org_id)
    if qs.model is Cliente:
        return qs.filter(organizacion_id=org_id)
    if qs.model is Proyecto:
        # Proyecto tiene FK organizacion
        return qs.filter(organizacion_id=org_id)
    return qs


@login_required
def users_list_api(request: HttpRequest):
    ctx = get_auth_context(request)
    qs = User.objects.all().select_related('usuarioperfiloptimizador')
    # Scope: por organización (usuarios de su org) salvo soporte
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        org_id = ctx.get('organization_id')
        qs = qs.filter(usuarioperfiloptimizador__organizacion_id=org_id)
    data = []
    for u in qs[:200]:
        role = None
        org = None
        try:
            role = u.usuarioperfiloptimizador.rol
            org = u.usuarioperfiloptimizador.organizacion.nombre if u.usuarioperfiloptimizador.organizacion else None
        except Exception:
            pass
        data.append({'id': u.id, 'username': u.username, 'role': role, 'organizacion': org})
    return JsonResponse({'users': data})


@login_required
def user_resumen_api(request: HttpRequest, user_id: int):
    ctx = get_auth_context(request)
    user = get_object_or_404(User, id=user_id)
    # Autorización: mismo scope de organización o soporte
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        try:
            user_org_id = user.usuarioperfiloptimizador.organizacion_id
        except Exception:
            user_org_id = None
        if user_org_id != ctx.get('organization_id'):
            return JsonResponse({'success': False, 'message': 'Forbidden'}, status=403)

    # Conteos
    proyectos_creados = Proyecto.objects.filter(creado_por=user).count()
    clientes_creados = Cliente.objects.filter(created_by=user).count()
    # Últimas 50 acciones de auditoría
    logs = AuditLog.objects.filter(actor=user).order_by('-created_at')[:50]
    acciones = [
        {
            'verb': l.verb,
            'target': f"{l.target_model}({l.target_id})",
            'at': l.created_at.strftime('%Y-%m-%d %H:%M'),
        }
        for l in logs
    ]
    perfil = None
    role = None
    org = None
    try:
        perfil = user.usuarioperfiloptimizador
        role = perfil.rol
        org = perfil.organizacion.nombre if perfil.organizacion else None
    except Exception:
        pass
    return JsonResponse({
        'success': True,
        'user': {
            'id': user.id,
            'username': user.username,
            'role': role,
            'organizacion': org,
            'proyectos_creados': proyectos_creados,
            'clientes_creados': clientes_creados,
            'acciones': acciones,
        }
    })


@login_required
def analytics_optimizations(request: HttpRequest):
    """GET /api/analytics/optimizations?start=YYYY-MM-DD&end=YYYY-MM-DD
    Retorna lista de eventos por día: [{title, start, allDay:true}]
    """
    import datetime as dt
    from django.db.models.functions import TruncDate
    from django.db.models import Count
    ctx = get_auth_context(request)
    start = request.GET.get('start')
    end = request.GET.get('end')
    try:
        start_d = dt.datetime.strptime(start, '%Y-%m-%d').date() if start else None
        end_d = dt.datetime.strptime(end, '%Y-%m-%d').date() if end else None
    except Exception:
        return JsonResponse({'success': False, 'message': 'Formato de fecha inválido'}, status=400)
    qs = OptimizationRun.objects.all()
    if not (ctx.get('organization_is_general') or ctx.get('is_support')):
        qs = qs.filter(organizacion_id=ctx.get('organization_id'))
    if start_d:
        qs = qs.filter(run_at__date__gte=start_d)
    if end_d:
        qs = qs.filter(run_at__date__lte=end_d)
    agg = qs.annotate(day=TruncDate('run_at')).values('day').annotate(count=Count('id')).order_by('day')
    events = [
        {
            'title': f"{row['count']} optimizaciones",
            'start': row['day'].isoformat(),
            'allDay': True,
        } for row in agg
    ]
    return JsonResponse({'success': True, 'events': events})
