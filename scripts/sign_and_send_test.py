"""Firma con xmlsec y envía a SUNAT beta (prueba)."""
import base64
import os
import sys
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

DS_NS = 'http://www.w3.org/2000/09/xmldsig#'
EXT_NS = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'


def firmar_xmlsec(unsigned_path: Path, signed_path: Path, sig_id: str = 'SignatureSP') -> None:
    root = etree.fromstring(unsigned_path.read_bytes())
    for sig in root.findall(f'.//{{{DS_NS}}}Signature'):
        sig.getparent().remove(sig)

    ext_content = root.find(f'.//{{{EXT_NS}}}ExtensionContent')
    if ext_content is None:
        raise ValueError('Falta ext:ExtensionContent')
    ext_content.clear()

    signature = xmlsec.template.create(
        root, xmlsec.Transform.EXCL_C14N, xmlsec.Transform.RSA_SHA256, ns='ds'
    )
    signature.set('Id', sig_id)
    ref = xmlsec.template.add_reference(signature, xmlsec.Transform.SHA256, uri='')
    xmlsec.template.add_transform(ref, xmlsec.Transform.ENVELOPED)
    xmlsec.template.add_transform(ref, xmlsec.Transform.EXCL_C14N)
    key_info = xmlsec.template.ensure_key_info(signature)
    x509_data = xmlsec.template.add_x509_data(key_info)
    pwd = getattr(settings, 'SUNAT_CERT_PASSWORD', '') or None
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

    out = etree.tostring(root, xml_declaration=True, encoding='UTF-8')
    out = out.replace(b"version='1.0'", b'version="1.0"')
    if b'xmlns:xsi=' in out:
        out = out.replace(
            b' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"', b''
        )
    signed_path.write_bytes(out)


if __name__ == '__main__':
    nombre = sys.argv[1] if len(sys.argv) > 1 else '20100070970-01-F001-00000072'
    src = BASE / 'storage' / 'xmls' / 'firmados' / '20100070970-01-F001-00000054.xml'
    dst = BASE / 'storage' / 'xmls' / 'firmados' / f'{nombre}.xml'

    # Clonar 54 → nuevo correlativo (sin firma previa)
    root = etree.fromstring(src.read_bytes())
    for sig in root.findall(f'.//{{{DS_NS}}}Signature'):
        sig.getparent().remove(sig)
    serie = '-'.join(nombre.split('-')[2:])
    for el in root.iter():
        if el.text and 'F001-00000054' in el.text:
            el.text = el.text.replace('F001-00000054', serie)
        if el.text and el.text == 'LlamaPeSign':
            pass
    for uri in root.iter('{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}URI'):
        if uri.text and uri.text.startswith('#'):
            uri.text = '#SignatureSP'
    for sid in root.findall(
        './/{urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2}Signature'
    ):
        id_el = sid.find('{urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2}ID')
        if id_el is not None:
            id_el.text = 'SignatureSP'

    tmp = BASE / 'storage' / 'xmls' / 'firmados' / '_unsigned_tmp.xml'
    tmp.write_bytes(etree.tostring(root, xml_declaration=True, encoding='UTF-8'))
    firmar_xmlsec(tmp, dst)
    tmp.unlink(missing_ok=True)
    print('Firmado:', dst)
    os.system(f'python "{BASE / "scripts" / "test_sunat_xmlsec.py"}" {nombre}')
