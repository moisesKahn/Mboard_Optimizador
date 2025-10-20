from django.shortcuts import redirect
from django.conf import settings
from django.urls import resolve


PUBLIC_PATH_PREFIXES = (
    '/authentication/signin/',
    '/authentication/forgot-password/',
    '/login/',
    '/logout/',
    '/auth/login',
    '/api/auth/login',
    settings.STATIC_URL,
    settings.MEDIA_URL,
)


class RequireLoginMiddleware:
    """Redirige a LOGIN_URL si el usuario no está autenticado.
    Excepciones: rutas de signin/logout, login API, y archivos estáticos/media.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        # Permitir prefijos públicos
        if any(path.startswith(p or '') for p in PUBLIC_PATH_PREFIXES if p):
            return self.get_response(request)

        # Si usuario no autenticado, redirigir a LOGIN_URL
        user = getattr(request, 'user', None)
        if not (user and user.is_authenticated):
            return redirect(settings.LOGIN_URL + f"?next={path}")

        return self.get_response(request)


class NoCacheMiddleware:
    """Evita que el navegador sirva páginas desde caché en vistas HTML.
    Aplica cabeceras no-store/no-cache a todas las respuestas text/html para impedir ver
    contenido al volver atrás tras logout (bfcache y cache del navegador).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            content_type = response.get('Content-Type', '')
        except Exception:
            content_type = ''
        if 'text/html' in content_type:
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
        return response
