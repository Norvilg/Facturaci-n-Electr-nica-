from django.shortcuts import redirect
from django.urls import resolve, Resolver404

RUTAS_PUBLICAS = {'login-page', 'auth-login', 'auth-refresh'}

PREFIJOS_PUBLICOS = ('/api/', '/admin/', '/static/', '/media/')


class AuthRedirectMiddleware:
    """
    Protege todas las vistas web HTML con JWT guardado en cookie.
    - Sin cookie access_token  → redirige a /login/
    - En /login/ con cookie    → redirige a /
    - Rutas /api/ y /admin/    → pasan directo (tienen su propia auth)
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # Dejar pasar rutas de API, admin y static
        for prefijo in PREFIJOS_PUBLICOS:
            if path.startswith(prefijo):
                return self.get_response(request)

        try:
            url_name = resolve(path).url_name
        except Resolver404:
            url_name = None

        es_publica   = url_name in RUTAS_PUBLICAS
        tiene_cookie = bool(request.COOKIES.get('access_token'))

        # En login con token → dashboard
        if url_name == 'login-page' and tiene_cookie:
            return redirect('/')

        # Ruta protegida sin token → login
        if not es_publica and not tiene_cookie:
            return redirect('/login/')

        return self.get_response(request)
