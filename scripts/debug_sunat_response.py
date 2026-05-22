"""Script temporal: captura respuesta cruda de SUNAT beta."""
import base64
import zipfile
from pathlib import Path

import requests

nombre = '20100070970-01-F001-00000059'
base = Path(__file__).resolve().parent.parent
xml_dir = base / 'storage' / 'xmls' / 'firmados'
ruta_xml = xml_dir / f'{nombre}.xml'
ruta_zip = xml_dir / f'{nombre}.zip'

with zipfile.ZipFile(ruta_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
    zf.write(ruta_xml, arcname=f'{nombre}.xml')
zip_b64 = base64.b64encode(ruta_zip.read_bytes()).decode('ascii')

url = 'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService'
log_dir = base / 'storage' / 'xmls' / 'logs'
log_dir.mkdir(parents=True, exist_ok=True)

for pwd in ('MODDATOS', 'moddatos'):
    soap = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.sunat.gob.pe" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
<soapenv:Header><wsse:Security><wsse:UsernameToken>
<wsse:Username>20100070970MODDATOS</wsse:Username>
<wsse:Password>{pwd}</wsse:Password>
</wsse:UsernameToken></wsse:Security></soapenv:Header>
<soapenv:Body><ser:sendBill>
<fileName>{nombre}.zip</fileName>
<contentFile>{zip_b64}</contentFile>
</ser:sendBill></soapenv:Body></soapenv:Envelope>"""

    r = requests.post(
        url,
        data=soap.encode('utf-8'),
        headers={
            'Content-Type': 'text/xml;charset=UTF-8',
            'SOAPAction': 'urn:sendBill',
        },
        timeout=30,
    )
    out = log_dir / f'respuesta_sunat_{pwd}.xml'
    out.write_bytes(r.content)
    print('password:', pwd, '| HTTP:', r.status_code, '| saved:', out)
    print(r.content[:1200].decode('utf-8', errors='replace'))
    print('-' * 60)
