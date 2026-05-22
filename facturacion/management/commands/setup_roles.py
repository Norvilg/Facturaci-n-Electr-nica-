"""Alias: use setup_usuarios para roles + usuarios."""
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Sincroniza roles (redirige a setup_usuarios)'

    def handle(self, *args, **options):
        call_command('setup_usuarios')
