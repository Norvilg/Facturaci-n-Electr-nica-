"""Firma con xmlsec (SignSUNAT) y envía a SUNAT beta."""
import base64
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import django
import xmlsec
from cryptography.hazmat.primitives.serialization import Encoding, pkcs12
from lxml import etree

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings

from facturacion.generarXmlFirmar import (
    SUNAT_CAC_SIGNATURE_ID,
    SUNAT_DS_SIGNATURE_ID,
    _ajustar_xml_ubl_sunat_beta,
    _normalizar_xml_firmado,
    enviar_xml_zipeado,
)
from sunat_py.ubl.builder import build_invoice_xml
from sunat_py.ubl.models import InvoiceInput, InvoiceLine, Party

DS_NS = 'http://www.w3.org/2000/09/xmldsig#'
EXT_NS = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'


def firmar_xmlsec(xml_str: str) -> bytes:
    root = etree.fromstring(xml_str.encode('utf-8'))
    for sig in root.findall(f'.//{{{DS_NS}}}Signature'):
        sig.getparent().remove(sig)
    ext_content = root.find(f'.//{{{EXT_NS}}}ExtensionContent')
    ext_content.clear()

    signature = xmlsec.template.create(
        root, xmlsec.Transform.EXCL_C14N, xmlsec.Transform.RSA_SHA256, ns='ds'
    )
    signature.set('Id', SUNAT_DS_SIGNATURE_ID)
    ref = xmlsec.template.add_reference(signature, xmlsec.Transform.SHA256, uri='')
    xmlsec.template.add_transform(ref, xmlsec.Transform.ENVELOPED)
    xmlsec.template.add_transform(ref, xmlsec.Transform.EXCL_C14N)
    key_info = xmlsec.template.ensure_key_info(signature)
    x509_data = xmlsec.template.add_x509_data(key_info)
    pwd = settings.SUNAT_CERT_PASSWORD or None
    with open(settings.SUNAT_CERT_PATH, 'rb') as f:
        _, certificate, _ = pkcs12.load_key_and_certificates(
            f.read(), pwd.encode() if pwd else None
        )
    cert_el = etree.SubElement(x509_data, f'{{{DS_NS}}}X509Certificate')
    cert_el.text = base64.b64encode(certificate.public_bytes(Encoding.DER)).decode('ascii')
    ext_content.append(signature)

    ctx = xmlsec.SignatureContext()
    ctx.key = xmlsec.Key.from_file(
        str(settings.SUNAT_CERT_PATH),
        xmlsec.constants.KeyDataFormatPkcs12,
        pwd,
    )
    ctx.sign(signature)
    return _normalizar_xml_firmado(
        etree.tostring(root, xml_declaration=True, encoding='UTF-8')
    )


numero = int(sys.argv[1]) if len(sys.argv) > 1 else 90
ruc = sys.argv[2] if len(sys.argv) > 2 else '20100066603'

inv = InvoiceInput(
    serie='F001',
    numero=numero,
    fecha_emision=date.today(),
    moneda='PEN',
    tipo_documento='01',
    emisor=Party('6', ruc, 'EMPRESA DEMO SAC', 'LIMA', '140101'),
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
import re

xml = re.sub(r'<cbc:ID>F001-\d+</cbc:ID>', f'<cbc:ID>{serie_num}</cbc:ID>', xml, count=1)

signed = firmar_xmlsec(xml)
base = f'{ruc}-01-F001-{numero:08d}'
Path(BASE / 'storage/xmls/firmados' / f'{base}.xml').write_bytes(signed)
print('Firmado xmlsec', SUNAT_DS_SIGNATURE_ID, SUNAT_CAC_SIGNATURE_ID)
print(enviar_xml_zipeado(base, signed, {'ruc': ruc, 'usuario_sol': 'MODDATOS', 'clave_sol': 'MODDATOS'}))
