"""Clona estructura de F001-00000052 (aceptada), re-firma y envía."""
import os
import sys
from datetime import date
from pathlib import Path

import django
from lxml import etree

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings

from facturacion.generarXmlFirmar import _firmar_xml, _normalizar_xml_firmado, enviar_xml_zipeado

NS_EXT = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'
NS_CBC = 'urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2'

src = BASE / 'storage/xmls/firmados/20100070970-01-F001-00000052.xml'
root = etree.parse(str(src)).getroot()
ext = root.find(f'.//{{{NS_EXT}}}ExtensionContent')
if ext is not None:
    ext.clear()

serie = f'F001-{int(sys.argv[1]):08d}' if len(sys.argv) > 1 else 'F001-00000102'
for el in root.iter(f'{{{NS_CBC}}}ID'):
    t = (el.text or '').strip()
    if t.startswith('F001-'):
        el.text = serie
for el in root.iter(f'{{{NS_CBC}}}IssueDate'):
    el.text = date.today().isoformat()

xml = etree.tostring(root, encoding='unicode')
xml = xml.replace('20100070970', '20100066603')
xml = xml.replace('F001-00000052', serie)
xml = xml.replace('#LlamaPeSign', '#SignatureSP')
if not xml.startswith('<?xml'):
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml

use_xfep = len(sys.argv) > 2 and sys.argv[2] == 'xfep'
if use_xfep:
    from xfep.sign import Certificate, XmlSigner

    signed = _normalizar_xml_firmado(
        XmlSigner.sign(
            xml.encode('utf-8'),
            Certificate.from_file(str(settings.SUNAT_CERT_PATH), settings.SUNAT_CERT_PASSWORD),
        )
    )
else:
    signed = _firmar_xml(xml)
nombre = f'20100066603-01-{serie}'
out = BASE / 'storage/xmls/firmados' / f'{nombre}.xml'
out.write_bytes(signed)
print('Guardado', out)
print(enviar_xml_zipeado(nombre, signed, {'ruc': '20100066603', 'usuario_sol': 'MODDATOS', 'clave_sol': 'MODDATOS'}))
