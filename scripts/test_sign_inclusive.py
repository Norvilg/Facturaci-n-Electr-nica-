"""Prueba firma C14N inclusivo (como factura aceptada F001-00000052)."""
import os
import re
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import django
from lxml import etree
from signxml import XMLSigner, methods

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings

from facturacion.generarXmlFirmar import (
    _ajustar_xml_ubl_sunat_beta,
    _normalizar_xml_firmado,
    enviar_xml_zipeado,
)
from facturacion.services_sunat import (
    ClienteProxy,
    ComprobanteProxy,
    DetalleProxy,
    EmpresaProxy,
    ProductoProxy,
    SerieProxy,
)
from sunat_py.security.cert_loader import load_cert_from_pfx
from sunat_py.ubl.builder import build_invoice_xml
from sunat_py.ubl.models import InvoiceInput, InvoiceLine, Party

NS_DS = 'http://www.w3.org/2000/09/xmldsig#'
NS_EXT = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'
SIG_ID = 'SignatureSP'


def firmar_inclusive(xml_str: str) -> bytes:
    cert = load_cert_from_pfx(
        Path(settings.SUNAT_CERT_PATH).read_bytes(),
        settings.SUNAT_CERT_PASSWORD,
    )
    root = etree.fromstring(xml_str.encode('utf-8'))
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm='rsa-sha256',
        digest_algorithm='sha256',
        c14n_algorithm='http://www.w3.org/TR/2001/REC-xml-c14n-20010315',
    )
    signed_root = signer.sign(root, key=cert.key_pem, cert=cert.cert_pem)
    signature = signed_root.find(f'{{{NS_DS}}}Signature')
    signature.set('Id', SIG_ID)
    ext_content = signed_root.find(
        f'{{{NS_EXT}}}UBLExtensions/{{{NS_EXT}}}UBLExtension/{{{NS_EXT}}}ExtensionContent'
    )
    signed_root.remove(signature)
    ext_content.append(signature)
    return _normalizar_xml_firmado(
        etree.tostring(signed_root, xml_declaration=True, encoding='UTF-8')
    )


numero = int(sys.argv[1]) if len(sys.argv) > 1 else 84
ruc = sys.argv[2] if len(sys.argv) > 2 else '20100066603'

inv = InvoiceInput(
    serie='F001',
    numero=numero,
    fecha_emision=date.today(),
    moneda='PEN',
    tipo_documento='01',
    emisor=Party('6', ruc, 'TU EMPRESA S.A.', 'LIMA', '140101'),
    receptor=Party('1', '10456789', 'JUAN PEREZ', 'TRUJILLO'),
    lines=[
        InvoiceLine(
            codigo='P001',
            descripcion='Producto demo',
            unidad='NIU',
            cantidad=Decimal('1'),
            precio_unitario=Decimal('100'),
            igv_afectacion='10',
        ),
    ],
)
xml = _ajustar_xml_ubl_sunat_beta(build_invoice_xml(inv))
serie_num = f'F001-{numero:08d}'
xml = re.sub(r'<cbc:ID>F001-\d+</cbc:ID>', f'<cbc:ID>{serie_num}</cbc:ID>', xml, count=1)

proxy = ComprobanteProxy(
    empresa=EmpresaProxy(ruc, 'TU EMPRESA S.A.', 'LIMA'),
    serie=SerieProxy('F001'),
    cliente=ClienteProxy('10456789', '1', 'JUAN PEREZ', 'TRUJILLO'),
    tipo='01',
    numero=numero,
    fecha_emision=date.today(),
    moneda='PEN',
    subtotal=Decimal('100'),
    igv=Decimal('18'),
    total=Decimal('118'),
    _detalles=[],
)
nombre = f'{ruc}-01-F001-{numero:08d}'
signed = firmar_inclusive(xml)
Path(BASE / 'storage/xmls/firmados' / f'{nombre}.xml').write_bytes(signed)
print('Firmado inclusivo:', nombre)
print(enviar_xml_zipeado(nombre, signed, {'ruc': ruc, 'usuario_sol': 'MODDATOS', 'clave_sol': 'MODDATOS'}))
