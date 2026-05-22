"""Prueba envío sin firma para ver siguiente error SUNAT."""
import base64
import os
import sys
import zipfile
from pathlib import Path

import django

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

import requests
from facturacion.generarXmlFirmar import generar_xml_y_firmar
from facturacion.services_sunat import (
    ComprobanteProxy,
    ClienteProxy,
    DetalleProxy,
    EmpresaProxy,
    ProductoProxy,
    SerieProxy,
)
from decimal import Decimal
from datetime import date

# Sin firma
import facturacion.generarXmlFirmar as gxf

gxf._firmar_xml = lambda xml: xml.encode('utf-8')

proxy = ComprobanteProxy(
    empresa=EmpresaProxy('20100070970', 'EMPRESA DEMO SAC', 'LIMA', 'MODDATOS', 'MODDATOS'),
    serie=SerieProxy('F001'),
    cliente=ClienteProxy('20555666777', '6', 'CLIENTE', 'LIMA'),
    tipo='01',
    numero=63,
    fecha_emision=date(2026, 5, 21),
    moneda='PEN',
    subtotal=Decimal('10'),
    igv=Decimal('1.8'),
    total=Decimal('11.8'),
    _detalles=[
        DetalleProxy(
            ProductoProxy('X', 'NIU', '10'),
            'ITEM',
            Decimal('1'),
            'NIU',
            Decimal('10'),
            Decimal('0'),
            Decimal('1.8'),
            Decimal('10'),
            Decimal('11.8'),
        )
    ],
)

xml = gxf.generar_xml_y_firmar(proxy)
nombre = proxy.nombre_archivo_sunat()
base = Path(__file__).resolve().parent.parent / 'storage' / 'xmls' / 'firmados'
base.mkdir(parents=True, exist_ok=True)
(base / f'{nombre}.xml').write_bytes(xml)
zip_path = base / f'{nombre}.zip'
with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.writestr(f'{nombre}.xml', xml)
zip_b64 = base64.b64encode(zip_path.read_bytes()).decode('ascii')

soap = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.sunat.gob.pe" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
<soapenv:Header><wsse:Security><wsse:UsernameToken>
<wsse:Username>20100070970MODDATOS</wsse:Username>
<wsse:Password>MODDATOS</wsse:Password>
</wsse:UsernameToken></wsse:Security></soapenv:Header>
<soapenv:Body><ser:sendBill>
<fileName>{nombre}.zip</fileName>
<contentFile>{zip_b64}</contentFile>
</ser:sendBill></soapenv:Body></soapenv:Envelope>"""

r = requests.post(
    'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService',
    data=soap.encode(),
    headers={'Content-Type': 'text/xml;charset=UTF-8', 'SOAPAction': 'urn:sendBill'},
    timeout=30,
)
print('HTTP', r.status_code)
print(r.text[:1500])
