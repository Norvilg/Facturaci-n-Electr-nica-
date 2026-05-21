from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import PerfilUsuario


class PerfilInline(admin.StackedInline):
    model       = PerfilUsuario
    can_delete  = False
    verbose_name = 'Perfil / Empresa'
    fields      = ['emisor']


class UsuarioAdmin(UserAdmin):
    inlines     = [PerfilInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'get_rol', 'get_emisor', 'is_active']
    list_filter  = ['groups', 'is_active']

    @admin.display(description='Rol')
    def get_rol(self, obj):
        g = obj.groups.first()
        return g.name if g else '-'

    @admin.display(description='Empresa')
    def get_emisor(self, obj):
        p = getattr(obj, 'perfil', None)
        return p.emisor if p else '-'


admin.site.unregister(User)
admin.site.register(User, UsuarioAdmin)
