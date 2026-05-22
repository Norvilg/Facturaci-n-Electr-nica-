"""
Envío a SUNAT beta (sendBill) — adaptado al flujo que ya conecta en pruebas.
Lee/escribe XML y ZIP en storage/xmls/firmados y storage/xmls/cdrs.
"""
import base64
import html
import logging
import os
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

def _sunat_beta_url() -> str:
    url = getattr(
        settings,
        'SUNAT_URL_BETA',
        'https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService',
    )
    return url.replace('?wsdl', '')


def _xml_firmados_dir() -> str:
    d = getattr(settings, 'XML_FIRMADOS_DIR', None)
    if d:
        return str(d)
    return os.path.join(settings.BASE_DIR, 'storage', 'xmls', 'firmados')


def _cdr_dir() -> str:
    d = getattr(settings, 'CDRS_DIR', None)
    if d:
        return str(d)
    return os.path.join(settings.BASE_DIR, 'storage', 'xmls', 'cdrs')


def _modo_sunat() -> str:
    return getattr(settings, 'SUNAT_MODO', 'beta').lower()


def _ruc_usuario_soap(credenciales: dict | None, nombre_comprobante: str) -> str:
    """RUC para WS-Security (debe coincidir con el certificado .pfx en beta)."""
    cred = credenciales or {}
    return (
        cred.get('ruc')
        or getattr(settings, 'SUNAT_CERT_RUC', '')
        or (nombre_comprobante.split('-')[0] if nombre_comprobante else '')
    )


def _mensaje_fault_amigable(codigo: str, fault: str) -> str:
    """Traduce faults SOAP frecuentes (el texto de SUNAT suele ser engañoso)."""
    if codigo == '2074':
        return (
            'SUNAT rechazó el XML (código 2074). El mensaje "UBLVersionID" suele ser '
            'genérico: UBL 2.1 + CustomizationID 2.0 son correctos. Revise firma '
            '(Id=SignatureSP, C14N inclusivo), PartyTaxScheme del emisor '
            '(TaxScheme/cbc:ID = RUC), TaxExemptionReasonCode cat. 07 (10), '
            'InvoiceTypeCode sin listID=0101, y credenciales 20100066603MODDATOS. '
            f'Detalle SUNAT: {fault}'
        )
    if codigo == '2335':
        return (
            'SUNAT: firma digital inválida o documento alterado (2335). '
            f'Detalle: {fault}'
        )
    if codigo == '0306':
        return (
            'SUNAT no pudo leer el XML (0306). Revise atributos no permitidos '
            f'(p. ej. Note con languageLocaleID). Detalle: {fault}'
        )
    if codigo in ('env:Client', 'Client') or 'internal error' in fault.lower():
        return (
            'SUNAT beta respondió error interno (servicio temporal o saturado). '
            'El XML suele ser válido en local; reintente en unos minutos. '
            f'Detalle: {fault}'
        )
    if codigo == '3205':
        return (
            'SUNAT: falta tipo de operación (cat. 51, ProfileID 0101). '
            f'Detalle: {fault}'
        )
    if codigo == '2800':
        return (
            'SUNAT: tipo de documento del receptor no permitido para esta factura. '
            'Use cliente con RUC (schemeID 6). '
            f'Detalle: {fault}'
        )
    return f'SUNAT: {fault}'


def enviar_xml_zipeado(
    nombre_comprobante: str,
    xml_firmado: bytes | None = None,
    credenciales: dict | None = None,
) -> dict:
    """
    Envía el comprobante a SUNAT beta o simula si SUNAT_MODO=simulado.

    Si recibe xml_firmado, lo guarda en firmados/{nombre}.xml antes de enviar.
    Si no, busca el XML ya guardado en disco (flujo original).
    """
    if _modo_sunat() == 'simulado':
        return _simular_envio(nombre_comprobante)

    xml_dir = _xml_firmados_dir()
    os.makedirs(xml_dir, exist_ok=True)

    ruta_xml = os.path.join(xml_dir, f'{nombre_comprobante}.xml')

    if xml_firmado:
        with open(ruta_xml, 'wb') as f:
            f.write(xml_firmado)
    elif not os.path.isfile(ruta_xml):
        return {
            'identificador': 'ERROR',
            'codigo': '404',
            'mensaje': 'No se encontró el XML firmado físico.',
            'cdr_file': '',
        }

    return _enviar_desde_disco(nombre_comprobante, credenciales)


def _enviar_desde_disco(nombre_comprobante: str, credenciales: dict | None = None) -> dict:
    """
    Toma el XML firmado de la carpeta, lo comprime en ZIP, envía SOAP a SUNAT
    y guarda el CDR de retorno.
    """
    xml_dir = _xml_firmados_dir()
    cdr_dir = _cdr_dir()
    os.makedirs(cdr_dir, exist_ok=True)

    ruta_xml = os.path.join(xml_dir, f'{nombre_comprobante}.xml')
    ruta_zip_envio = os.path.join(xml_dir, f'{nombre_comprobante}.zip')
    ruta_zip_cdr = os.path.join(cdr_dir, f'R-{nombre_comprobante}.zip')
    nombre_cdr_xml = f'R-{nombre_comprobante}.xml'
    ruta_cdr_xml = os.path.join(cdr_dir, nombre_cdr_xml)

    if not os.path.isfile(ruta_xml):
        return {
            'identificador': 'ERROR',
            'codigo': '404',
            'mensaje': 'No se encontró el XML firmado físico.',
            'cdr_file': '',
        }

    cred = credenciales or {}
    ruc_emisor = _ruc_usuario_soap(credenciales, nombre_comprobante)
    usuario_sol = cred.get('usuario_sol') or getattr(settings, 'SUNAT_USUARIO_SOL', 'MODDATOS')
    clave_sol = cred.get('clave_sol') or getattr(settings, 'SUNAT_CLAVE_SOL', 'MODDATOS')

    try:
        with zipfile.ZipFile(ruta_zip_envio, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.write(ruta_xml, arcname=f'{nombre_comprobante}.xml')

        with open(ruta_zip_envio, 'rb') as f:
            zip_bytes = f.read()

        resultado_zeep = _enviar_con_sunat_py(
            zip_bytes, nombre_comprobante, ruc_emisor, usuario_sol, clave_sol,
            ruta_zip_cdr, ruta_cdr_xml, nombre_cdr_xml, cdr_dir,
        )
        if resultado_zeep is not None:
            return resultado_zeep

        zip_content_b64 = base64.b64encode(zip_bytes).decode('utf-8')

        soap_envelope = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.sunat.gob.pe" xmlns:wsse="http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd">
    <soapenv:Header>
        <wsse:Security>
            <wsse:UsernameToken>
                <wsse:Username>{ruc_emisor}{usuario_sol}</wsse:Username>
                <wsse:Password>{clave_sol}</wsse:Password>
            </wsse:UsernameToken>
        </wsse:Security>
    </soapenv:Header>
    <soapenv:Body>
        <ser:sendBill>
            <fileName>{nombre_comprobante}.zip</fileName>
            <contentFile>{zip_content_b64}</contentFile>
        </ser:sendBill>
    </soapenv:Body>
</soapenv:Envelope>"""

        headers = {
            'Content-Type': 'text/xml;charset=UTF-8',
            'SOAPAction': 'urn:sendBill',
        }

        response = requests.post(
            _sunat_beta_url(),
            data=soap_envelope.encode('utf-8'),
            headers=headers,
            timeout=30,
        )

        _guardar_log_respuesta_sunat(nombre_comprobante, response.content)

        if response.status_code in (200, 500):
            resultado = _procesar_respuesta_soap(
                response.content,
                nombre_comprobante,
                ruta_zip_cdr,
                ruta_cdr_xml,
                nombre_cdr_xml,
                cdr_dir,
            )
            if resultado:
                return resultado

        mensaje_http = (
            _extraer_fault_soap(response.content)
            or f'Error HTTP {response.status_code} del servidor SUNAT.'
        )
        return {
            'identificador': 'ERROR_SOAP',
            'codigo': str(response.status_code),
            'mensaje': mensaje_http,
            'cdr_file': '',
        }

    except requests.RequestException as e:
        logger.error('Error de conexión con SUNAT: %s', e, exc_info=True)
        return {
            'identificador': 'FALLO_CONEXION',
            'codigo': '500',
            'mensaje': f'No se pudo conectar con el servidor SUNAT: {e}',
            'cdr_file': '',
        }
    except Exception as e:
        logger.error('Error enviando a SUNAT: %s', e, exc_info=True)
        return {
            'identificador': 'ERROR',
            'codigo': '9999',
            'mensaje': str(e),
            'cdr_file': '',
        }


def _guardar_log_respuesta_sunat(nombre_comprobante: str, content: bytes) -> None:
    try:
        log_dir = Path(settings.BASE_DIR) / 'storage' / 'xmls' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / f'ultima_respuesta_{nombre_comprobante}.xml').write_bytes(content)
    except Exception:
        pass


def _local_tag(tag: str) -> str:
    return tag.split('}')[-1] if '}' in tag else tag


def _extraer_cdr_b64(content: bytes) -> str | None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None

    candidatos = ('applicationResponse', 'return', 'content')
    for elem in root.iter():
        if _local_tag(elem.tag) in candidatos and elem.text and len(elem.text.strip()) > 100:
            return elem.text.strip()
    return None


def _extraer_codigo_fault(content: bytes) -> str:
    try:
        root = ET.fromstring(content)
        for elem in root.iter():
            if _local_tag(elem.tag) == 'faultcode' and elem.text:
                return elem.text.split('.')[-1].strip()
    except ET.ParseError:
        pass
    return '99'


def _procesar_respuesta_soap(
    content: bytes,
    nombre_comprobante: str,
    ruta_zip_cdr: str,
    ruta_cdr_xml: str,
    nombre_cdr_xml: str,
    cdr_dir: str,
) -> dict | None:
    """Procesa CDR o Fault SOAP devuelto por SUNAT."""
    fault = _extraer_fault_soap(content)
    cdr_b64 = _extraer_cdr_b64(content)

    if cdr_b64:
        cdr_bytes = base64.b64decode(cdr_b64)
        with open(ruta_zip_cdr, 'wb') as f:
            f.write(cdr_bytes)

        cdr_xml = _extraer_xml_desde_zip_cdr(cdr_bytes)
        if cdr_xml:
            with open(ruta_cdr_xml, 'w', encoding='utf-8') as f:
                f.write(cdr_xml)
        else:
            with zipfile.ZipFile(ruta_zip_cdr, 'r') as zip_ref:
                zip_ref.extractall(cdr_dir)

        codigo, mensaje = _leer_codigo_cdr(ruta_cdr_xml)
        if codigo == '0':
            return {
                'identificador': 'ACEPTADO',
                'codigo': codigo,
                'mensaje': mensaje or (
                    f'Comprobante aceptado por SUNAT. CDR: {nombre_cdr_xml}'
                ),
                'cdr_file': nombre_cdr_xml,
            }
        return {
            'identificador': 'RECHAZADO',
            'codigo': codigo,
            'mensaje': mensaje or 'SUNAT rechazó el comprobante.',
            'cdr_file': nombre_cdr_xml if os.path.isfile(ruta_cdr_xml) else '',
        }

    if fault:
        codigo = _extraer_codigo_fault(content)
        return {
            'identificador': 'RECHAZADO',
            'codigo': codigo,
            'mensaje': _mensaje_fault_amigable(codigo, fault),
            'cdr_file': '',
        }

    return None


def _enviar_con_sunat_py(
    zip_bytes: bytes,
    nombre_comprobante: str,
    ruc_emisor: str,
    usuario_sol: str,
    clave_sol: str,
    ruta_zip_cdr: str,
    ruta_cdr_xml: str,
    nombre_cdr_xml: str,
    cdr_dir: str,
) -> dict | None:
    """Envío vía cliente zeep de sunat-py (mismo WSDL oficial)."""
    if not getattr(settings, 'SUNAT_USE_ZEEP', False):
        return None
    try:
        from sunat_py.sunat.client import build_zeep_client, send_bill
        from sunat_py.sunat.packager import unpack_cdr
    except ImportError:
        return None

    try:
        client = build_zeep_client('beta', ruc_emisor, usuario_sol, clave_sol)
        result = send_bill(client, zip_bytes, f'{nombre_comprobante}.zip')
    except Exception as exc:
        logger.warning('sunat-py send_bill no disponible (%s); se usa SOAP manual.', exc)
        return None

    if result.cdr_xml:
        cdr_bytes = result.cdr_xml
        if cdr_bytes[:2] == b'PK':
            with open(ruta_zip_cdr, 'wb') as f:
                f.write(cdr_bytes)
            try:
                cdr_bytes = unpack_cdr(cdr_bytes)
            except Exception:
                pass
        with open(ruta_cdr_xml, 'wb') as f:
            f.write(cdr_bytes)

    codigo = result.code or '99'
    if result.status in ('accepted', 'accepted_with_obs'):
        return {
            'identificador': 'ACEPTADO',
            'codigo': codigo,
            'mensaje': result.description or f'Comprobante aceptado. CDR: {nombre_cdr_xml}',
            'cdr_file': nombre_cdr_xml if os.path.isfile(ruta_cdr_xml) else '',
        }
    return {
        'identificador': 'RECHAZADO',
        'codigo': codigo,
        'mensaje': _mensaje_fault_amigable(codigo, result.description or ''),
        'cdr_file': '',
    }


def _extraer_xml_desde_zip_cdr(cdr_zip_bytes: bytes) -> str:
    try:
        import io
        with zipfile.ZipFile(io.BytesIO(cdr_zip_bytes), 'r') as zf:
            for name in zf.namelist():
                if name.lower().endswith('.xml'):
                    return zf.read(name).decode('utf-8')
    except Exception:
        pass
    return ''


def _leer_codigo_cdr(ruta_cdr_xml: str) -> tuple[str, str]:
    if not os.path.isfile(ruta_cdr_xml):
        return '0', ''
    try:
        root = ET.parse(ruta_cdr_xml).getroot()
        codigo = '0'
        mensaje = ''
        observaciones = []
        for elem in root.iter():
            tag = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
            if tag == 'ResponseCode' and elem.text is not None:
                codigo = elem.text.strip()
            elif tag == 'Description' and elem.text and not mensaje:
                mensaje = html.unescape(elem.text.strip())
            elif tag == 'Note' and elem.text:
                nota = html.unescape(elem.text.strip())
                if nota and nota not in observaciones:
                    observaciones.append(nota)
        if codigo == '0' and observaciones:
            mensaje = (
                (mensaje + ' ') if mensaje else ''
            ) + f"(Observaciones SUNAT: {' | '.join(observaciones)})"
        return codigo, mensaje
    except Exception:
        return '0', ''


def _extraer_fault_soap(content: bytes) -> str:
    try:
        root = ET.fromstring(content)
        for elem in root.iter():
            if _local_tag(elem.tag) == 'faultstring' and elem.text:
                return html.unescape(elem.text.strip())
    except Exception:
        pass
    return ''


def _simular_envio(nombre_comprobante: str) -> dict:
    """Modo local sin red (tests / desarrollo)."""
    cdr_dir = _cdr_dir()
    os.makedirs(cdr_dir, exist_ok=True)
    nombre_cdr = f'R-{nombre_comprobante}.xml'
    ruta_cdr = os.path.join(cdr_dir, nombre_cdr)

    partes = nombre_comprobante.split('-')
    ruc_emisor = partes[0] if partes else '20123456789'
    tipo_comp = partes[1] if len(partes) > 1 else '01'
    serie_correlativo = '-'.join(partes[2:]) if len(partes) > 2 else 'F001-00000012'
    hoy = date.today().isoformat()

    cdr_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<ApplicationResponse xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"
                     xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
                     xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cac:DocumentResponse>
        <cac:Response>
            <cbc:ResponseCode>0</cbc:ResponseCode>
            <cbc:Description><![CDATA[Aceptado (modo simulado). {tipo_comp} {serie_correlativo}]]></cbc:Description>
        </cac:Response>
    </cac:DocumentResponse>
</ApplicationResponse>"""
    try:
        with open(ruta_cdr, 'w', encoding='utf-8') as f:
            f.write(cdr_xml)
        return {
            'identificador': 'ACEPTADO',
            'codigo': '0',
            'mensaje': f'Comprobante aceptado (simulado). CDR: {nombre_cdr}',
            'cdr_file': nombre_cdr,
        }
    except OSError as e:
        return {
            'identificador': 'ERROR',
            'codigo': '9999',
            'mensaje': str(e),
            'cdr_file': '',
        }
