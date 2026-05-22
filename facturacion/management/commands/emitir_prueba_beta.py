"""
Emite una factura F001 de prueba (genera XML, firma, envía a SUNAT).

Uso:
  python manage.py emitir_prueba_beta
  python manage.py emitir_prueba_beta 140
  python manage.py emitir_prueba_beta --simulado
  python manage.py emitir_prueba_beta 140 --solo-generar
"""
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from facturacion.catalogos_sunat import codigo_afectacion_igv
from facturacion.generarXmlFirmar import enviar_xml_zipeado, generar_xml_y_firmar
from facturacion.models import TipoAfectacion
from facturacion.services_sunat import (
    ClienteProxy,
    ComprobanteProxy,
    DetalleProxy,
    EmpresaProxy,
    ProductoProxy,
    SerieProxy,
)


def _siguiente_correlativo() -> int:
    """Siguiente F001-NNNNNNNN (8 digitos, rango habitual SUNAT)."""
    firmados = Path(settings.XML_FIRMADOS_DIR)
    maximo = 0
    if firmados.is_dir():
        for archivo in firmados.glob('20100066603-01-F001-*.xml'):
            parte = archivo.stem.split('-')[-1]
            if parte.isdigit() and len(parte) == 8:
                n = int(parte)
                if 1 <= n < 99_999_999:
                    maximo = max(maximo, n)
    return max(maximo + 1, 1)


def _validar_xml_local(xml_bytes: bytes) -> tuple[bool, str]:
    try:
        from signxml import XMLVerifier
        from sunat_py.security.cert_loader import load_cert_from_pfx
        from sunat_py.xsd import validate_signed_xml

        from facturacion.generarXmlFirmar import _validar_xsd_curso

        validate_signed_xml(xml_bytes)
        if getattr(settings, 'SUNAT_XSD_INVOICE_21', ''):
            _validar_xsd_curso(xml_bytes, '01')
        cert_path = Path(settings.SUNAT_CERT_PATH)
        bundle = load_cert_from_pfx(
            cert_path.read_bytes(),
            getattr(settings, 'SUNAT_CERT_PASSWORD', '') or None,
        )
        XMLVerifier().verify(xml_bytes, x509_cert=bundle.cert_pem)
        xsd_msg = 'sunat-py + XSD curso' if getattr(settings, 'SUNAT_XSD_INVOICE_21', '') else 'sunat-py'
        return True, f'XSD ({xsd_msg}) y firma OK (local)'
    except Exception as exc:
        return False, str(exc)[:200]


class Command(BaseCommand):
    help = 'Genera, firma y envía factura F001 de prueba a SUNAT (beta o simulado)'

    def add_arguments(self, parser):
        parser.add_argument(
            'numero',
            nargs='?',
            type=int,
            help='Correlativo (ej. 140). Si se omite, usa el siguiente libre en firmados/',
        )
        parser.add_argument(
            '--simulado',
            action='store_true',
            help='Fuerza SUNAT_MODO=simulado (CDR local aceptado)',
        )
        parser.add_argument(
            '--solo-generar',
            action='store_true',
            help='Solo genera y guarda XML firmado, sin enviar',
        )
        parser.add_argument(
            '--ruc',
            default='20100066603',
            help='RUC emisor (debe coincidir con el .pfx)',
        )
        parser.add_argument(
            '--cliente-ruc',
            default='20555666777',
            help='RUC del receptor (factura exige schemeID 6)',
        )

    def handle(self, *args, **options):
        if options['simulado']:
            settings.SUNAT_MODO = 'simulado'
        else:
            settings.SUNAT_MODO = 'beta'
            settings.SUNAT_USE_ZEEP = True

        ruc = options['ruc']
        numero = options['numero'] or _siguiente_correlativo()
        serie_num = f'F001-{numero:08d}'
        modo = getattr(settings, 'SUNAT_MODO', 'beta')

        for ta in TipoAfectacion.objects.all():
            nuevo = codigo_afectacion_igv(ta.codigo)
            if ta.codigo != nuevo:
                ta.codigo = nuevo
                ta.save(update_fields=['codigo'])
                self.stdout.write(f'  Catalogo: {ta.descripcion} -> codigo {nuevo!r}')

        proxy = ComprobanteProxy(
            empresa=EmpresaProxy(
                ruc,
                'TU EMPRESA S.A.',
                'AV. PRINCIPAL 123 - LIMA',
                'MODDATOS',
                'MODDATOS',
            ),
            serie=SerieProxy('F001'),
            cliente=ClienteProxy(
                options['cliente_ruc'],
                '6',
                'COMERCIAL EL SOL EIRL',
                'CALLE LAS FLORES 89 - CHICLAYO',
            ),
            tipo='01',
            numero=numero,
            fecha_emision=date.today(),
            moneda='PEN',
            subtotal=Decimal('85.00'),
            igv=Decimal('15.30'),
            total=Decimal('100.30'),
            _detalles=[
                DetalleProxy(
                    producto=ProductoProxy('Licencia Office 365 (1 anio)', 'NIU', '10'),
                    descripcion='Licencia Office 365 (1 anio)',
                    cantidad=Decimal('1'),
                    unidad_medida='NIU',
                    precio_unitario=Decimal('85.00'),
                    descuento=Decimal('0'),
                    igv_linea=Decimal('15.30'),
                    subtotal=Decimal('85.00'),
                    total=Decimal('100.30'),
                ),
            ],
        )

        nombre = proxy.nombre_archivo_sunat()
        self.stdout.write(f'Modo: {modo}')
        self.stdout.write(f'Comprobante: {serie_num} ({nombre})')

        xml_bytes = generar_xml_y_firmar(proxy)
        ruta_xml = Path(settings.XML_FIRMADOS_DIR) / f'{nombre}.xml'
        ruta_xml.write_bytes(xml_bytes)

        checks = []
        texto = xml_bytes.decode('utf-8', errors='replace')
        checks.append(('TaxExemptionReasonCode=10', 'catalogo07">10<' in texto))
        checks.append(('InvoiceTypeCode listID=0101', 'listID="0101"' in texto and 'catalogo51' in texto))
        checks.append(('IDSignSP', 'IDSignSP' in texto))
        checks.append(('SignatureSP', 'Id="SignatureSP"' in texto))
        for etiqueta, ok in checks:
            self.stdout.write(self.style.SUCCESS(f'  OK {etiqueta}') if ok else self.style.ERROR(f'  FALTA {etiqueta}'))

        ok_local, msg_local = _validar_xml_local(xml_bytes)
        if ok_local:
            self.stdout.write(self.style.SUCCESS(f'  {msg_local}'))
        else:
            self.stdout.write(self.style.WARNING(f'  Validacion local: {msg_local}'))

        self.stdout.write(f'XML: {ruta_xml} ({len(xml_bytes)} bytes)')

        if options['solo_generar']:
            self.stdout.write(self.style.SUCCESS('Listo (solo XML, sin envio).'))
            return

        resultado = enviar_xml_zipeado(
            nombre,
            xml_bytes,
            credenciales={
                'ruc': ruc,
                'usuario_sol': 'MODDATOS',
                'clave_sol': 'MODDATOS',
            },
        )

        ident = resultado.get('identificador', '')
        codigo = resultado.get('codigo', '')
        mensaje = resultado.get('mensaje', '')
        cdr = resultado.get('cdr_file', '')

        if ident == 'ACEPTADO':
            self.stdout.write(self.style.SUCCESS(f'ACEPTADO codigo={codigo} CDR={cdr}'))
            self.stdout.write(mensaje)
            self.stdout.write(self.style.SUCCESS(
                f'Listo para exposicion: {serie_num} aceptado. CDR en storage/xmls/cdrs/'
            ))
            return

        self.stdout.write(self.style.ERROR(f'RECHAZADO codigo={codigo}'))
        self.stdout.write(mensaje)

        if ok_local and modo == 'beta' and codigo in ('2074', '2335', 'env:Client'):
            self.stdout.write(self.style.WARNING(
                'El XML es valido localmente; beta SUNAT rechazo el envio. '
                'Revise storage/xmls/logs/ultima_respuesta_*.xml y reintente mas tarde.'
            ))
