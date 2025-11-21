import threading
from typing import Optional

_thread_locals = threading.local()


def get_current_request():
    return getattr(_thread_locals, 'request', None)


def get_current_user():
    req = get_current_request()
    if not req:
        return None
    try:
        return getattr(req, 'user', None)
    except Exception:
        return None


class RequestUserMiddleware:
    """Middleware minimal que guarda la request actual en una variable thread-local.

    Esto permite que señales y otros hooks accedan al usuario que originó la petición
    sin requerir modificar todas las llamadas manualmente.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Guardar la request en el hilo actual
        try:
            _thread_locals.request = request
        except Exception:
            pass

        response = self.get_response(request)

        # Intentamos limpiar la referencia para evitar fugas de memoria en servidores persistentes
        try:
            if hasattr(_thread_locals, 'request'):
                del _thread_locals.request
        except Exception:
            pass

        return response


class AutoServicioIsolationMiddleware:
    """Aísla el flujo para usuarios con rol 'autoservicio'.
    Si el usuario autenticado tiene perfil autoservicio, sólo se permiten rutas bajo
    '/autoservicio/' (landing, hub y APIs), además de login/logout y estáticos.
    Cualquier otra ruta se redirige a la landing autoservicio.
    """
    ALLOWED_PREFIXES = ['/autoservicio/', '/logout/', '/login/']

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            user = getattr(request, 'user', None)
            if user and user.is_authenticated:
                perfil = getattr(user, 'usuarioperfiloptimizador', None)
                if perfil and perfil.rol == 'autoservicio':
                    path = request.path
                    # Permitir estáticos/media
                    from django.conf import settings
                    if path.startswith(settings.STATIC_URL) or path.startswith(settings.MEDIA_URL):
                        return self.get_response(request)
                    if not any(path.startswith(p) for p in self.ALLOWED_PREFIXES):
                        from django.shortcuts import redirect
                        return redirect('/autoservicio/')
            return self.get_response(request)
        except Exception:
            return self.get_response(request)
