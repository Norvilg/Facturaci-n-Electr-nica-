"""Crea los 3 roles, 3 usuarios y muestra credenciales de acceso."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from facturacion.roles import (
    ALL_CUSTOM_PERMS,
    APP_LABEL,
    ROLES,
    ROLES_OBSOLETOS,
    USUARIOS_SISTEMA,
)


class Command(BaseCommand):
    help = 'Configura 3 roles (Administrador, Contador, Emisor) y 3 usuarios'

    def handle(self, *args, **options):
        permisos = self._cargar_permisos()
        if not permisos:
            return

        self._sincronizar_roles(permisos)
        self._eliminar_roles_obsoletos()
        self._sincronizar_usuarios()
        self._mostrar_credenciales()

    def _cargar_permisos(self):
        permisos = {}
        for codename in ALL_CUSTOM_PERMS:
            try:
                permisos[codename] = Permission.objects.get(
                    content_type__app_label=APP_LABEL,
                    codename=codename,
                )
            except Permission.DoesNotExist:
                self.stderr.write(
                    self.style.ERROR(
                        f'Permiso {APP_LABEL}.{codename} no existe. '
                        'Ejecute: python manage.py migrate'
                    )
                )
                return None
        return permisos

    def _sincronizar_roles(self, permisos):
        for nombre_rol, codenames in ROLES.items():
            grupo, creado = Group.objects.get_or_create(name=nombre_rol)
            grupo.permissions.set([permisos[c] for c in codenames])
            accion = 'Creado' if creado else 'Actualizado'
            self.stdout.write(
                self.style.SUCCESS(
                    f'{accion} rol "{nombre_rol}" ({len(codenames)} permisos).'
                )
            )

    def _eliminar_roles_obsoletos(self):
        borrados, _ = Group.objects.filter(name__in=ROLES_OBSOLETOS).delete()
        if borrados:
            self.stdout.write(
                self.style.WARNING(f'Eliminados {borrados} rol(es) antiguo(s).')
            )

    def _sincronizar_usuarios(self):
        User = get_user_model()
        usernames = {u['username'] for u in USUARIOS_SISTEMA}

        # Dejar solo los 3 usuarios del sistema
        eliminados, _ = User.objects.exclude(username__in=usernames).delete()
        if eliminados:
            self.stdout.write(
                self.style.WARNING(
                    f'Eliminados {eliminados} usuario(s) que no son del sistema.'
                )
            )

        for datos in USUARIOS_SISTEMA:
            grupo = Group.objects.get(name=datos['rol'])
            user, creado = User.objects.get_or_create(
                username=datos['username'],
                defaults={
                    'email': datos['email'],
                    'is_staff': datos['is_staff'],
                    'is_superuser': datos['is_superuser'],
                },
            )
            user.email = datos['email']
            user.is_staff = datos['is_staff']
            user.is_superuser = datos['is_superuser']
            user.is_active = True
            user.set_password(datos['password'])
            user.save()
            user.groups.set([grupo])

            accion = 'Creado' if creado else 'Actualizado'
            self.stdout.write(
                self.style.SUCCESS(
                    f'{accion} usuario "{datos["username"]}" -> rol {datos["rol"]}.'
                )
            )

    def _mostrar_credenciales(self):
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO('=== CREDENCIALES DE ACCESO (/login/) ==='))
        self.stdout.write('')
        for datos in USUARIOS_SISTEMA:
            self.stdout.write(
                f'  Rol: {datos["rol"]:14}  Usuario: {datos["username"]:14}  '
                f'Contrasena: {datos["password"]}'
            )
        self.stdout.write('')
        self.stdout.write(
            self.style.WARNING(
                'Cambie las contrasenas en produccion. Login: http://127.0.0.1:8000/login/'
            )
        )
