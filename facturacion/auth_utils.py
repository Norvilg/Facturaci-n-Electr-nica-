"""Utilidades de autenticación y control por roles."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from .roles import APP_LABEL, RUTAS_POST_LOGIN


def permiso_completo(codename: str) -> str:
    return f'{APP_LABEL}.{codename}'


def usuario_tiene_permiso(user, codename: str) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.has_perm(permiso_completo(codename))


def permisos_usuario(user) -> dict[str, bool]:
    """Mapa codename → bool para plantillas y menú."""
    from .roles import ALL_CUSTOM_PERMS

    if not user.is_authenticated:
        return {c: False for c in ALL_CUSTOM_PERMS}
    if user.is_superuser:
        return {c: True for c in ALL_CUSTOM_PERMS}
    return {c: user.has_perm(permiso_completo(c)) for c in ALL_CUSTOM_PERMS}


def nombre_rol_usuario(user) -> str:
    if not user.is_authenticated:
        return ''
    if user.is_superuser:
        return 'Superusuario'
    grupo = user.groups.order_by('name').first()
    return grupo.name if grupo else 'Sin rol asignado'


def url_inicio_usuario(user):
    from django.urls import reverse

    for codename, url_name in RUTAS_POST_LOGIN:
        if usuario_tiene_permiso(user, codename):
            return reverse(url_name)
    return reverse('login')


def permiso_requerido(codename: str):
    """Exige login y permiso del rol; superusuario siempre pasa."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if usuario_tiene_permiso(request.user, codename):
                return view_func(request, *args, **kwargs)

            es_api = (
                request.path.startswith('/api/')
                or request.content_type == 'application/json'
                or 'application/json' in request.headers.get('Accept', '')
            )
            if es_api or request.method == 'POST':
                return JsonResponse(
                    {
                        'success': False,
                        'error': 'No tiene permiso para realizar esta operación.',
                    },
                    status=403,
                )
            return render(
                request,
                '403.html',
                {
                    'permiso_requerido': codename,
                    'rol_usuario': nombre_rol_usuario(request.user),
                },
                status=403,
            )

        return wrapper

    return decorator
