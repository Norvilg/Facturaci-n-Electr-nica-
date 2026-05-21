from rest_framework.permissions import BasePermission


def _grupo(user, nombre):
    return user.groups.filter(name=nombre).exists()


class EsAdmin(BasePermission):
    message = 'Acceso restringido a administradores.'
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (_grupo(request.user, 'admin') or request.user.is_superuser))


class EsAdminOEmisor(BasePermission):
    message = 'Solo administradores y emisores pueden operar comprobantes.'
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (_grupo(request.user, 'admin') or
                     _grupo(request.user, 'emisor') or
                     request.user.is_superuser))


class EsAdminOContador(BasePermission):
    message = 'Solo administradores y contadores pueden ver reportes.'
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (_grupo(request.user, 'admin') or
                     _grupo(request.user, 'contador') or
                     request.user.is_superuser))


class PerteneceAlEmisor(BasePermission):
    """
    Admin ve todo. Emisor/contador solo ven comprobantes de su empresa.
    El objeto debe tener id_emisor (Comprobante).
    """
    message = 'No tienes acceso a recursos de otra empresa.'

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or _grupo(request.user, 'admin'):
            return True
        perfil    = getattr(request.user, 'perfil', None)
        emisor_id = perfil.emisor_id if perfil else None
        if not emisor_id:
            return False
        obj_emisor = getattr(obj, 'id_emisor_id',
                    getattr(obj, 'emisor_id', None))
        return emisor_id == obj_emisor
