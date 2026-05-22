"""Corrige catálogos mal cargados (tipo afectación IGV 1000 → 10)."""
from django.core.management.base import BaseCommand

from facturacion.catalogos_sunat import codigo_afectacion_igv
from facturacion.models import TipoAfectacion


class Command(BaseCommand):
    help = 'Corrige codigo de tipo_afectacion (1000 → 10) según catálogo SUNAT 07'

    def handle(self, *args, **options):
        actualizados = 0
        for ta in TipoAfectacion.objects.all():
            nuevo = codigo_afectacion_igv(ta.codigo)
            if ta.codigo != nuevo:
                self.stdout.write(
                    f'  {ta.codigo!r} -> {nuevo!r} ({ta.descripcion})'
                )
                ta.codigo = nuevo
                ta.save(update_fields=['codigo'])
                actualizados += 1
        if actualizados:
            self.stdout.write(self.style.SUCCESS(f'Actualizados: {actualizados}'))
        else:
            self.stdout.write(self.style.SUCCESS('Catálogos ya correctos.'))
