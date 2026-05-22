"""Prueba sunat-py: UBL + firma + envío beta."""
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import django

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings

from sunat_py.security.cert_loader import load_cert_from_pfx
from sunat_py.signer.xmldsig import sign_invoice_xml
from sunat_py.sunat.client import send_bill
from sunat_py.sunat.packager import pack_invoice
from sunat_py.ubl.builder import build_invoice_xml
from sunat_py.ubl.models import InvoiceInput, InvoiceLine, Party

numero = int(sys.argv[1]) if len(sys.argv) > 1 else 80
ruc = sys.argv[2] if len(sys.argv) > 2 else '20100066603'

invoice = InvoiceInput(
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

pfx_bytes = Path(settings.SUNAT_CERT_PATH).read_bytes()
cert = load_cert_from_pfx(pfx_bytes, settings.SUNAT_CERT_PASSWORD)
xml = build_invoice_xml(invoice)
signed = sign_invoice_xml(xml, cert)
base_name = f'{ruc}-01-F001-{numero}'
out = BASE / 'storage' / 'xmls' / 'firmados' / f'{base_name}.xml'
out.write_bytes(signed)
print('XML guardado', out)

from sunat_py.sunat.client import build_zeep_client, send_bill

client = build_zeep_client('beta', ruc, 'MODDATOS', 'MODDATOS')
zip_bytes = pack_invoice(signed, base_name)
result = send_bill(client, zip_bytes, f'{base_name}.zip')
print('status:', result.status, 'code:', result.code)
print('desc:', result.description[:200] if result.description else '')
if result.cdr_xml:
    cdr_path = BASE / 'storage' / 'xmls' / 'cdrs' / f'R-{base_name}.xml'
    cdr_path.write_bytes(result.cdr_xml)
    print('CDR guardado:', cdr_path)
