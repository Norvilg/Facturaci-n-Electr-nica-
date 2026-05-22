import os
import re
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from lxml import etree
from .catalogos_sunat import codigo_afectacion_igv
from .services_sunat_conexion import enviar_xml_zipeado

logger = logging.getLogger(__name__)

# Estándar SUNAT (catálogo firma XMLDSig en ExtensionContent)
SUNAT_DS_SIGNATURE_ID = 'SignSUNAT'
SUNAT_CAC_SIGNATURE_ID = 'IDSignSUNAT'

# Registrar los namespaces globales para evitar prefijos incorrectos en el XML
namespaces = {
    "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
    "ds": "http://www.w3.org/2000/09/xmldsig#"
}
for prefix, uri in namespaces.items():
    ET.register_namespace(prefix, uri)

# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES DE DISCO (PERSISTENCIA DE ARCHIVOS)
# ─────────────────────────────────────────────────────────────────────────────

def guardar_archivo_disco(contenido, ruta_completa: str) -> str:
    directorio = os.path.dirname(ruta_completa)
    os.makedirs(directorio, exist_ok=True)
    with open(ruta_completa, 'wb') as f:
        if isinstance(contenido, str):
            contenido = contenido.encode('utf-8')
        f.write(contenido)
    return os.path.relpath(ruta_completa, settings.BASE_DIR)


def obtener_xml_firmado_disco(comprobante) -> str:
    if not comprobante.nombrexml:
        return None
    xml_dir = getattr(settings, 'XML_FIRMADOS_DIR', os.path.join(settings.BASE_DIR, 'storage', 'xmls', 'firmados'))
    ruta_completa = os.path.join(xml_dir, comprobante.nombrexml)
    if not os.path.exists(ruta_completa):
        return None
    with open(ruta_completa, 'r', encoding='utf-8') as f:
        return f.read()


def obtener_cdr_disco(comprobante) -> str:
    if not hasattr(comprobante, 'sunat_cdr') or not comprobante.sunat_cdr:
        return None
    cdr_dir = getattr(settings, 'CDRS_DIR', os.path.join(settings.BASE_DIR, 'storage', 'xmls', 'cdrs'))
    ruta_completa = os.path.join(cdr_dir, comprobante.sunat_cdr)
    if not os.path.exists(ruta_completa):
        return None
    with open(ruta_completa, 'r', encoding='utf-8') as f:
        return f.read()


# ─────────────────────────────────────────────────────────────────────────────
# MOTOR DE GENERACIÓN Y FIRMADO CRIPTOGRÁFICO
# ─────────────────────────────────────────────────────────────────────────────

def _buscar_pfx_en_carpetas(base: Path) -> Path | None:
    """Busca el primer .pfx en core/certs o certs/ del proyecto."""
    for carpeta in (base / 'core' / 'certs', base / 'certs'):
        if not carpeta.is_dir():
            continue
        preferido = carpeta / 'DEMO_Sunat.pfx'
        if preferido.is_file():
            return preferido.resolve()
        for archivo in sorted(carpeta.glob('*.pfx')):
            return archivo.resolve()
    return None


def _ruta_certificado() -> Path:
    """Ruta absoluta al .pfx (evita concatenar mal BASE_DIR + 'core/certs/...')."""
    base = Path(settings.BASE_DIR).resolve()

    env_cert = os.environ.get('SUNAT_CERT_PATH', '').strip()
    if env_cert:
        p = Path(os.path.normpath(env_cert))
        return p.resolve() if p.is_absolute() else (base / p).resolve()

    cert = getattr(settings, 'SUNAT_CERT_PATH', None)
    if cert:
        p = Path(os.path.normpath(str(cert)))
        if p.is_file():
            return p.resolve()
        if p.is_absolute():
            encontrado = _buscar_pfx_en_carpetas(base)
            if encontrado:
                return encontrado
            return p.resolve()
        candidato = (base.joinpath(*p.parts)).resolve()
        if candidato.is_file():
            return candidato

    encontrado = _buscar_pfx_en_carpetas(base)
    if encontrado:
        return encontrado

    return (base / 'core' / 'certs' / 'DEMO_Sunat.pfx').resolve()


def _normalizar_xml_firmado(signed_bytes: bytes) -> bytes:
    """Ajustes menores exigidos por el validador SUNAT (declaración XML, certificado)."""
    signed_bytes = signed_bytes.replace(b"encoding='UTF-8' standalone='no'", b'encoding="UTF-8"')
    signed_bytes = signed_bytes.replace(b"encoding='UTF-8'", b'encoding="UTF-8"')
    signed_bytes = signed_bytes.replace(b" standalone='no'", b'')
    signed_bytes = signed_bytes.replace(b"version='1.0'", b'version="1.0"')
    signed_bytes = signed_bytes.replace(
        b' xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"', b''
    )
    signed_bytes = re.sub(
        br'(<ds:X509Certificate[^>]*>)(.*?)(</ds:X509Certificate>)',
        lambda m: m.group(1) + m.group(2).replace(b'\n', b'') + m.group(3),
        signed_bytes,
        flags=re.DOTALL,
    )
    return signed_bytes


def _ruc_desde_certificado() -> str | None:
    """Extrae el RUC del subject del .pfx (DEMO SUNAT: ... RUC 20XXXXXXXXX ...)."""
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    cert_path = _ruta_certificado()
    if not cert_path.is_file():
        return None
    pwd = getattr(settings, 'SUNAT_CERT_PASSWORD', '') or None
    try:
        with open(cert_path, 'rb') as f:
            _, cert, _ = pkcs12.load_key_and_certificates(
                f.read(), pwd.encode() if pwd else None
            )
        if not cert:
            return None
        for attr in cert.subject:
            texto = str(attr.value)
            if 'RUC' in texto.upper():
                import re as _re
                m = _re.search(r'(\d{11})', texto)
                if m:
                    return m.group(1)
        attrs = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)
        for attr in attrs:
            m = re.search(r'(\d{11})', str(attr.value))
            if m:
                return m.group(1)
    except Exception:
        return None
    return None


def _total_en_letras_soles(total) -> str:
    """Monto total en letras (catálogo SUNAT 52, código 1000)."""
    from decimal import Decimal

    def bajo(num):
        if num == 0:
            return 'CERO'
        unidades = ('', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE')
        especiales = (
            'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISEIS', 'DIECISIETE',
            'DIECIOCHO', 'DIECINUEVE',
        )
        decenas = ('', '', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA', 'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA')
        centenas = (
            '', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 'QUINIENTOS',
            'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS',
        )
        if num < 10:
            return unidades[num]
        if num < 20:
            return especiales[num - 10]
        if num < 100:
            d, u = divmod(num, 10)
            if u == 0:
                return decenas[d]
            if d == 2:
                return 'VEINTI' + unidades[u]
            return decenas[d] + ' Y ' + unidades[u]
        if num == 100:
            return 'CIEN'
        c, r = divmod(num, 100)
        return (centenas[c] + (' ' + bajo(r) if r else '')).strip()

    monto = Decimal(str(total)).quantize(Decimal('0.01'))
    entero = int(monto)
    centavos = int((monto - Decimal(entero)) * 100)
    partes = []
    millones, resto = divmod(entero, 1_000_000)
    miles, resto = divmod(resto, 1000)
    if millones:
        partes.append(bajo(millones) + ' MILLON' + ('ES' if millones > 1 else ''))
    if miles:
        partes.append(('UN MIL' if miles == 1 else bajo(miles) + ' MIL').strip())
    if resto or not partes:
        partes.append(bajo(resto))
    letras = ' '.join(partes)
    return f'SON {letras} CON {centavos:02d}/100 SOLES'


def _firmar_xml(xml_str: str) -> bytes:
    """
    Firma UBL en ExtensionContent (XMLDSig RSA-SHA256 + C14N exclusivo, estándar SUNAT).
    """
    from signxml import XMLSigner, methods
    from sunat_py.security.cert_loader import load_cert_from_pfx

    cert_path = _ruta_certificado()
    if not cert_path.is_file():
        destino = Path(settings.BASE_DIR).resolve() / 'core' / 'certs' / 'DEMO_Sunat.pfx'
        raise FileNotFoundError(
            f'Certificado SUNAT no encontrado.\n'
            f'Buscado en: {cert_path}\n'
            f'Copie su archivo .pfx a: {destino}'
        )

    pwd = getattr(settings, 'SUNAT_CERT_PASSWORD', '') or None
    bundle = load_cert_from_pfx(cert_path.read_bytes(), pwd)
    root = etree.fromstring(xml_str.encode('utf-8'))
    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm='rsa-sha256',
        digest_algorithm='sha256',
        c14n_algorithm='http://www.w3.org/2001/10/xml-exc-c14n#',
    )
    signed_root = signer.sign(root, key=bundle.key_pem, cert=bundle.cert_pem)

    ns_ds = 'http://www.w3.org/2000/09/xmldsig#'
    ns_ext = 'urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2'
    signature = signed_root.find(f'{{{ns_ds}}}Signature')
    if signature is None:
        raise RuntimeError('No se generó ds:Signature en el XML.')
    signature.set('Id', SUNAT_DS_SIGNATURE_ID)

    ext_content = signed_root.find(
        f'{{{ns_ext}}}UBLExtensions/{{{ns_ext}}}UBLExtension/{{{ns_ext}}}ExtensionContent'
    )
    if ext_content is None:
        raise ValueError('Falta ext:ExtensionContent en el XML UBL.')
    signed_root.remove(signature)
    ext_content.append(signature)

    signed_bytes = etree.tostring(
        signed_root, xml_declaration=True, encoding='UTF-8', pretty_print=False
    )
    return _normalizar_xml_firmado(signed_bytes)


def _ajustar_xml_ubl_sunat_beta(xml: str) -> str:
    """
    Ajustes post-build para validación SUNAT beta.
    listID=0101 en InvoiceTypeCode provoca error 2074 (es código de operación, no de documento).
    """
    xml = re.sub(
        r'<cbc:InvoiceTypeCode[^>]*>(\d+)</cbc:InvoiceTypeCode>',
        r'<cbc:InvoiceTypeCode>\1</cbc:InvoiceTypeCode>',
        xml,
    )
    xml = re.sub(
        r'<cbc:ProfileID[^>]*>([^<]+)</cbc:ProfileID>',
        r'<cbc:ProfileID>\1</cbc:ProfileID>',
        xml,
    )
    xml = re.sub(
        r'<cbc:DocumentCurrencyCode[^>]*>([^<]+)</cbc:DocumentCurrencyCode>',
        r'<cbc:DocumentCurrencyCode>\1</cbc:DocumentCurrencyCode>',
        xml,
    )
    xml = re.sub(r'\s*<cbc:IssueTime>[^<]*</cbc:IssueTime>\s*', '\n', xml)
    xml = re.sub(r'\s*<cbc:Note[^>]*>.*?</cbc:Note>\s*', '\n', xml, flags=re.DOTALL)
    # TaxCategory global sin cbc:ID falla validación XSD (error 2074 genérico).
    xml = re.sub(
        r'(<cac:TaxTotal>\s*<cbc:TaxAmount[^>]*>[^<]+</cbc:TaxAmount>\s*<cac:TaxSubtotal>.*?<cac:TaxCategory>)\s*<cac:TaxScheme>',
        r'\1<cbc:ID>S</cbc:ID><cac:TaxScheme>',
        xml,
        count=1,
        flags=re.DOTALL,
    )
    xml = re.sub(
        r'(<cac:InvoiceLine>.*?<cac:TaxCategory>)\s*<cbc:Percent>',
        r'\1<cbc:ID>S</cbc:ID><cbc:Percent>',
        xml,
        flags=re.DOTALL,
    )
    xml = re.sub(
        r'\s*<cac:SellersItemIdentification>.*?</cac:SellersItemIdentification>',
        '',
        xml,
        flags=re.DOTALL,
    )
    xml = xml.replace('#SignatureSP', f'#{SUNAT_DS_SIGNATURE_ID}')
    xml = re.sub(
        r'(<cac:Signature>\s*<cbc:ID>)[^<]+(</cbc:ID>)',
        rf'\1{SUNAT_CAC_SIGNATURE_ID}\2',
        xml,
        count=1,
    )
    return xml


def _proxy_a_invoice_input(comprobante_proxy):
    """Mapea ComprobanteProxy → sunat_py.ubl.models.InvoiceInput."""
    from decimal import Decimal

    from sunat_py.ubl.models import InvoiceInput, InvoiceLine, Party

    tipo_doc = str(comprobante_proxy.cliente.tipo_documento)
    if tipo_doc == '6':
        tipo_receptor = '6'
    elif tipo_doc in ('1', '01'):
        tipo_receptor = '1'
    else:
        tipo_receptor = tipo_doc

    lineas = []
    for idx, det in enumerate(comprobante_proxy.detalles.all(), start=1):
        afectacion = codigo_afectacion_igv(det.producto.tipo_afectacion_igv)
        lineas.append(
            InvoiceLine(
                codigo=f'ITEM{idx:03d}',
                descripcion=det.descripcion[:250],
                unidad=det.unidad_medida or 'NIU',
                cantidad=Decimal(str(det.cantidad)),
                precio_unitario=Decimal(str(det.precio_unitario)),
                igv_afectacion=afectacion,
            )
        )

    tipo_comp = comprobante_proxy.tipo if comprobante_proxy.tipo in ('01', '03') else '01'
    return InvoiceInput(
        serie=comprobante_proxy.serie.serie,
        numero=int(comprobante_proxy.numero),
        fecha_emision=comprobante_proxy.fecha_emision,
        moneda=comprobante_proxy.moneda or 'PEN',
        tipo_documento=tipo_comp,
        emisor=Party(
            tipo_doc='6',
            numero_doc=comprobante_proxy.empresa.ruc,
            razon_social=comprobante_proxy.empresa.razon_social[:100],
            direccion=(comprobante_proxy.empresa.direccion or 'LIMA')[:100],
            ubigeo='140101',
        ),
        receptor=Party(
            tipo_doc=tipo_receptor,
            numero_doc=str(comprobante_proxy.cliente.numero_documento)[:20],
            razon_social=comprobante_proxy.cliente.razon_social[:100],
            direccion=(comprobante_proxy.cliente.direccion or '-')[:100],
        ),
        lines=lineas,
    )


def _generar_xml_sunat_py(comprobante_proxy) -> bytes:
    """
    Genera y firma UBL 2.1 con plantilla sunat-py (estructura validada por SUNAT).
    """
    from sunat_py.ubl.builder import build_invoice_xml

    inv = _proxy_a_invoice_input(comprobante_proxy)
    xml = _ajustar_xml_ubl_sunat_beta(build_invoice_xml(inv))

    serie_num = (
        f'{comprobante_proxy.serie.serie}-{int(comprobante_proxy.numero):08d}'
    )
    xml = re.sub(
        rf'<cbc:ID>{re.escape(comprobante_proxy.serie.serie)}-\d+</cbc:ID>',
        f'<cbc:ID>{serie_num}</cbc:ID>',
        xml,
        count=1,
    )

    return _firmar_xml(xml)


def generar_xml_y_firmar(comprobante_proxy) -> bytes:
    """
    Construye el XML completo de SUNAT (UBL 2.1) incluyendo ítems dinámicos,
    bloque de impuestos globales e inyecta la firma criptográfica del certificado.
    """
    try:
        return _generar_xml_sunat_py(comprobante_proxy)
    except Exception as exc:
        logger.warning('sunat-py no generó el XML (%s); se usa plantilla local.', exc)

    fecha_emision = str(comprobante_proxy.fecha_emision)
    serie_num = f'{comprobante_proxy.serie.serie}-{comprobante_proxy.numero:08d}'
    igv_pct = int(getattr(settings, 'IGV_PORCENTAJE', 0.18) * 100)
    ruc_emisor = comprobante_proxy.empresa.ruc

    # 1. Construcción dinámica de las líneas de productos (InvoiceLine)
    items_xml_str = ""
    for idx, det in enumerate(comprobante_proxy.detalles.all(), start=1):
        # El tipo de precio (01 = precio con IGV, que es el valor de catálogo estándar de SUNAT)
        items_xml_str += f"""
    <cac:InvoiceLine>
        <cbc:ID>{idx}</cbc:ID>
        <cbc:InvoicedQuantity unitCode="{det.unidad_medida}">{det.cantidad:.2f}</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="{comprobante_proxy.moneda}">{det.subtotal:.2f}</cbc:LineExtensionAmount>
        <cac:PricingReference>
            <cac:AlternativeConditionPrice>
                <cbc:PriceAmount currencyID="{comprobante_proxy.moneda}">{(det.total / det.cantidad):.2f}</cbc:PriceAmount>
                <cbc:PriceTypeCode>01</cbc:PriceTypeCode>
            </cac:AlternativeConditionPrice>
        </cac:PricingReference>
        <cac:TaxTotal>
            <cbc:TaxAmount currencyID="{comprobante_proxy.moneda}">{det.igv_linea:.2f}</cbc:TaxAmount>
            <cac:TaxSubtotal>
                <cbc:TaxableAmount currencyID="{comprobante_proxy.moneda}">{det.subtotal:.2f}</cbc:TaxableAmount>
                <cbc:TaxAmount currencyID="{comprobante_proxy.moneda}">{det.igv_linea:.2f}</cbc:TaxAmount>
                <cac:TaxCategory>
                    <cbc:ID>S</cbc:ID>
                    <cbc:Percent>{igv_pct:.2f}</cbc:Percent>
                    <cbc:TaxExemptionReasonCode>{codigo_afectacion_igv(det.producto.tipo_afectacion_igv)}</cbc:TaxExemptionReasonCode>
                    <cac:TaxScheme>
                        <cbc:ID>1000</cbc:ID>
                        <cbc:Name>IGV</cbc:Name>
                        <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
                    </cac:TaxScheme>
                </cac:TaxCategory>
            </cac:TaxSubtotal>
        </cac:TaxTotal>
        <cac:Item>
            <cbc:Description><![CDATA[{det.descripcion}]]></cbc:Description>
        </cac:Item>
        <cac:Price>
            <cbc:PriceAmount currencyID="{comprobante_proxy.moneda}">{det.precio_unitario:.2f}</cbc:PriceAmount>
        </cac:Price>
    </cac:InvoiceLine>"""

    # 2. Estructura UBL (firma digital se inyecta después con el .pfx)
    xml_str = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
         xmlns:ext="urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
         xmlns:ds="http://www.w3.org/2000/09/xmldsig#">
    <ext:UBLExtensions>
        <ext:UBLExtension>
            <ext:ExtensionContent/>
        </ext:UBLExtension>
    </ext:UBLExtensions>
    <cbc:UBLVersionID>2.1</cbc:UBLVersionID>
    <cbc:CustomizationID>2.0</cbc:CustomizationID>
    <cbc:ProfileID>0101</cbc:ProfileID>
    <cbc:ID>{serie_num}</cbc:ID>
    <cbc:IssueDate>{fecha_emision}</cbc:IssueDate>
    <cbc:InvoiceTypeCode>{comprobante_proxy.tipo}</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>{comprobante_proxy.moneda}</cbc:DocumentCurrencyCode>
    <cac:Signature>
        <cbc:ID>{SUNAT_CAC_SIGNATURE_ID}</cbc:ID>
        <cac:SignatoryParty>
            <cac:PartyIdentification>
                <cbc:ID>{ruc_emisor}</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
                <cbc:Name><![CDATA[{comprobante_proxy.empresa.razon_social}]]></cbc:Name>
            </cac:PartyName>
        </cac:SignatoryParty>
        <cac:DigitalSignatureAttachment>
            <cac:ExternalReference>
                <cbc:URI>#{SUNAT_DS_SIGNATURE_ID}</cbc:URI>
            </cac:ExternalReference>
        </cac:DigitalSignatureAttachment>
    </cac:Signature>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeID="6">{ruc_emisor}</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyTaxScheme>
                <cbc:RegistrationName><![CDATA[{comprobante_proxy.empresa.razon_social}]]></cbc:RegistrationName>
                <cbc:CompanyID schemeID="6">{ruc_emisor}</cbc:CompanyID>
                <cac:TaxScheme><cbc:ID>{ruc_emisor}</cbc:ID></cac:TaxScheme>
            </cac:PartyTaxScheme>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA[{comprobante_proxy.empresa.razon_social}]]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cbc:ID>140101</cbc:ID>
                    <cbc:AddressTypeCode>0000</cbc:AddressTypeCode>
                    <cac:AddressLine><cbc:Line><![CDATA[{comprobante_proxy.empresa.direccion}]]></cbc:Line></cac:AddressLine>
                    <cac:Country><cbc:IdentificationCode>PE</cbc:IdentificationCode></cac:Country>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyIdentification>
                <cbc:ID schemeID="{comprobante_proxy.cliente.tipo_documento}">{comprobante_proxy.cliente.numero_documento}</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyLegalEntity>
                <cbc:RegistrationName><![CDATA[{comprobante_proxy.cliente.razon_social}]]></cbc:RegistrationName>
                <cac:RegistrationAddress>
                    <cac:AddressLine><cbc:Line><![CDATA[{comprobante_proxy.cliente.direccion}]]></cbc:Line></cac:AddressLine>
                    <cac:Country><cbc:IdentificationCode>PE</cbc:IdentificationCode></cac:Country>
                </cac:RegistrationAddress>
            </cac:PartyLegalEntity>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:PaymentTerms>
        <cbc:ID>FormaPago</cbc:ID>
        <cbc:PaymentMeansID>Contado</cbc:PaymentMeansID>
    </cac:PaymentTerms>
    <cac:TaxTotal>
        <cbc:TaxAmount currencyID="{comprobante_proxy.moneda}">{comprobante_proxy.igv:.2f}</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount currencyID="{comprobante_proxy.moneda}">{comprobante_proxy.subtotal:.2f}</cbc:TaxableAmount>
            <cbc:TaxAmount currencyID="{comprobante_proxy.moneda}">{comprobante_proxy.igv:.2f}</cbc:TaxAmount>
            <cac:TaxCategory>
                <cbc:ID>S</cbc:ID>
                <cac:TaxScheme>
                    <cbc:ID>1000</cbc:ID>
                    <cbc:Name>IGV</cbc:Name>
                    <cbc:TaxTypeCode>VAT</cbc:TaxTypeCode>
                </cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="{comprobante_proxy.moneda}">{comprobante_proxy.subtotal:.2f}</cbc:LineExtensionAmount>
        <cbc:TaxInclusiveAmount currencyID="{comprobante_proxy.moneda}">{comprobante_proxy.total:.2f}</cbc:TaxInclusiveAmount>
        <cbc:PayableAmount currencyID="{comprobante_proxy.moneda}">{comprobante_proxy.total:.2f}</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>{items_xml_str}
</Invoice>
"""
    return _firmar_xml(xml_str)



def enviar_a_sunat(comprobante_proxy) -> dict:
    try:
        modo = getattr(settings, 'SUNAT_MODO', 'beta').lower()
        ruc_cert = _ruc_desde_certificado()
        if (
            modo != 'simulado'
            and ruc_cert
            and comprobante_proxy.empresa.ruc != ruc_cert
        ):
            return {
                'estado': 'RECHAZADO',
                'codigo': 'CERT_RUC',
                'descripcion': (
                    f'El RUC del emisor ({comprobante_proxy.empresa.ruc}) no coincide con '
                    f'el certificado digital ({ruc_cert}). En SUNAT beta configure el emisor '
                    f'con RUC {ruc_cert} y usuario/clave MODDATOS.'
                ),
                'ticket': '',
            }

        # 1. Generamos y firmamos el XML con tus productos dinámicos
        xml_bytes = generar_xml_y_firmar(comprobante_proxy)
        if modo != 'simulado':
            try:
                from sunat_py.xsd import validate_signed_xml

                validate_signed_xml(xml_bytes)
            except Exception as xsd_err:
                logger.warning('Validación XSD local: %s', xsd_err)
        base_nombre = comprobante_proxy.nombre_archivo_sunat() # Ejemplo: '20123456789-01-F001-00000011'
        nombre_archivo = f"{base_nombre}.xml"
        comprobante_proxy.xml_firmado = nombre_archivo
        
        # 2. Guardamos físicamente en la carpeta de firmados
        ruta_guardado = os.path.join(settings.BASE_DIR, 'storage', 'xmls', 'firmados', nombre_archivo)
        guardar_archivo_disco(xml_bytes, ruta_guardado)
        
        ruc_soap = ruc_cert or comprobante_proxy.empresa.ruc
        credenciales = {
            'ruc': ruc_soap,
            'usuario_sol': comprobante_proxy.empresa.usuario_sol or getattr(
                settings, 'SUNAT_USUARIO_SOL', 'MODDATOS'
            ),
            'clave_sol': comprobante_proxy.empresa.clave_sol or getattr(
                settings, 'SUNAT_CLAVE_SOL', 'MODDATOS'
            ),
        }
        resultado_sunat = enviar_xml_zipeado(
            base_nombre, xml_bytes, credenciales=credenciales
        )
        
        ident = resultado_sunat.get('identificador', 'ERROR')
        if ident == 'ACEPTADO':
            comprobante_proxy.sunat_cdr = resultado_sunat.get('cdr_file', '')
            return {
                'estado': 'ACEPTADO',
                'codigo': resultado_sunat.get('codigo', '0'),
                'descripcion': resultado_sunat['mensaje'],
                'ticket': f'SUNAT-{base_nombre}',
            }

        return {
            'estado': 'RECHAZADO',
            'codigo': resultado_sunat.get('codigo', '99'),
            'descripcion': resultado_sunat['mensaje'],
            'ticket': '',
        }
            
    except Exception as e:
        logger.error(f"Error en flujo enviar_a_sunat: {e}", exc_info=True)
        return {
            'estado': 'RECHAZADO',
            'codigo': '9999',
            'descripcion': f'Error en procesamiento o respuesta: {str(e)}',
            'ticket': '',
        }