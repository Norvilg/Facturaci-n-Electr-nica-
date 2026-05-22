"""Alinea el emisor de la BD con el RUC del certificado .pfx (SUNAT beta)."""
from django.conf import settings
from django.core.management.base import BaseCommand

from facturacion.generarXmlFirmar import _ruc_desde_certificado
from facturacion.models import Emisor


class Command(BaseCommand):
    help = (
        'Actualiza usuario_sol/clave_sol a MODDATOS y el RUC del emisor '
        'para que coincida con el certificado digital configurado.'
    )

    def handle(self, *args, **options):
        ruc_cert = _ruc_desde_certificado() or getattr(settings, 'SUNAT_CERT_RUC', '')
        if not ruc_cert:
            self.stderr.write('No se pudo leer el RUC del certificado .pfx.')
            return

        actualizados = 0
        for emisor in Emisor.objects.all():
            cambios = []
            if emisor.ruc != ruc_cert:
                self.stdout.write(
                    f'Emisor {emisor.id_emisor}: RUC {emisor.ruc} -> {ruc_cert}'
                )
                emisor.ruc = ruc_cert
                cambios.append('ruc')
            if emisor.usuario_sol != 'MODDATOS':
                emisor.usuario_sol = 'MODDATOS'
                cambios.append('usuario_sol')
            if emisor.clave_sol != 'MODDATOS':
                emisor.clave_sol = 'MODDATOS'
                cambios.append('clave_sol')
            if cambios:
                emisor.save(update_fields=cambios)
                actualizados += 1

        if actualizados:
            self.stdout.write(
                self.style.SUCCESS(
                    f'{actualizados} emisor(es) alineado(s) con certificado {ruc_cert}.'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Emisor(es) ya coinciden con {ruc_cert}.')
            )
