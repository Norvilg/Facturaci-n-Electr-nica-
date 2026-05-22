"""Envío de prueba a SUNAT beta con XML firmado por xmlsec."""
import base64
import html
import os
import re
import sys
import zipfile
from pathlib import Path

import django
import requests

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

nombre = sys.argv[1] if len(sys.argv) > 1 else '20100070970-01-F001-00000071'
xml_path = BASE / 'storage' / 'xmls' / 'firmados' / f'{nombre}.xml'
zip_path = BASE / 'storage' / 'xmls' / 'firmados' / f'{nombre}.zip'
log_path = BASE / 'storage' / 'xmls' / 'logs' / f'ultima_respuesta_{nombre}.xml'

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(xml_path, arcname=f'{nombre}.xml')

zip_b64 = base64.b64encode(zip_path.read_bytes()).decode('ascii')
soap = (
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" '
    'xmlns:ser="http://service.sunat.gob.pe" '
    'xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">'
    '<soapenv:Header><wsse:Security><wsse:UsernameToken>'
    '<wsse:Username>20100070970MODDATOS</wsse:Username>'
    '<wsse:Password>MODDATOS</wsse:Password>'
    '</wsse:UsernameToken></wsse:Security></soapenv:Header>'
    '<soapenv:Body><ser:sendBill>'
    f'<fileName>{nombre}.zip</fileName>'
    f'<contentFile>{zip_b64}</contentFile>'
    '</ser:sendBill></soapenv:Body></soapenv:Envelope>'
)

r = requests.post(
    'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService',
    data=soap.encode('utf-8'),
    headers={
        'Content-Type': 'text/xml;charset=UTF-8',
        'SOAPAction': 'urn:sendBill',
    },
    timeout=60,
)
log_path.parent.mkdir(parents=True, exist_ok=True)
log_path.write_bytes(r.content)
print('HTTP', r.status_code, '| log:', log_path)
text = r.text
if 'applicationResponse' in text:
    print('OK: SUNAT devolvió CDR (applicationResponse)')
else:
    m = re.search(r'faultstring>([^<]+)', text)
    if m:
        print('FAULT:', html.unescape(m.group(1))[:600])
