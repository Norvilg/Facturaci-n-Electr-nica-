from django.shortcuts import redirect
from django.urls import resolve

# Rutas que NO requieren autenticación
RUTAS_PUBLICAS = [
    'login-page',
    'auth-login',
    'auth-refresh',
]

# Prefijos de URL que no se interceptan
PREFIJOS_PUBLICOS = [
    '/api/',
    '/admin/',
]


class AuthMiddleware:
    """
    Middleware que protege todas las vistas web (HTML).
    - Si el usuario accede a cualquier ruta sin token → redirige a /login/
    - Si accede a /login/ con token válido → redirige a /
    - Las rutas /api/ no se interceptan (tienen su propia auth JWT)
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path

        # No interceptar rutas de API ni admin ni static
        for prefijo in PREFIJOS_PUBLICOS:
            if path.startswith(prefijo):
                return self.get_response(request)

        # Resolver el nombre de la vista actual
        try:
            url_name = resolve(path).url_name
        except Exception:
            url_name = None

        es_publica = url_name in RUTAS_PUBLICAS
        tiene_token = bool(request.COOKIES.get('access_token'))

        # Si está en login y tiene token → ir al dashboard
        if url_name == 'login-page' and tiene_token:
            return redirect('/')

        # Si NO es ruta pública y no tiene token → ir al login
        if not es_publica and not tiene_token:
            return redirect('/login/')

        return self.get_response(request)
