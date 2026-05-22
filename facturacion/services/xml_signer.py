import os
import re
from pathlib import Path

from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)
from cryptography.hazmat.primitives.serialization import pkcs12
from django.conf import settings
from lxml import etree
from signxml import XMLSigner, methods

from facturacion.constants import ESTADO_FIRMADO
from facturacion.services.xml_builder import (
    NS_CBC,
    NS_DS,
    NS_EXT,
    generar_xml_comprobante,
    nombre_archivo_sunat,
)


CANONICALIZATION_ALGORITHM = "http://www.w3.org/TR/2001/REC-xml-c14n-20010315"


class FirmaDigitalError(Exception):
    pass


def cargar_certificado_pfx():
    """Carga private key y certificado desde el PFX configurado en settings/.env."""
    cert_path = getattr(settings, "SUNAT_CERT_PATH", "")
    cert_password = getattr(settings, "SUNAT_CERT_PASSWORD", "")

    if not cert_path:
        raise FirmaDigitalError("SUNAT_CERT_PATH no esta configurado.")
    if not cert_password:
        raise FirmaDigitalError("SUNAT_CERT_PASSWORD no esta configurado.")

    ruta = Path(cert_path)
    if not ruta.is_absolute():
        ruta = Path(settings.BASE_DIR) / ruta

    if not ruta.exists():
        raise FirmaDigitalError(f"No existe el certificado PFX: {ruta}")

    try:
        pfx_data = ruta.read_bytes()
        private_key, certificate, additional_certs = pkcs12.load_key_and_certificates(
            pfx_data,
            cert_password.encode("utf-8"),
        )
    except Exception as exc:
        raise FirmaDigitalError(f"No se pudo cargar el PFX: {exc}") from exc

    if private_key is None or certificate is None:
        raise FirmaDigitalError("El PFX no contiene private key o certificado.")

    return private_key, certificate, additional_certs


def convertir_certificado_a_pem(private_key, certificate):
    """Convierte private key y certificado a PEM para signxml."""
    try:
        key_pem = private_key.private_bytes(
            encoding=Encoding.PEM,
            format=PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=NoEncryption(),
        )
        cert_pem = certificate.public_bytes(encoding=Encoding.PEM)
    except Exception as exc:
        raise FirmaDigitalError(f"No se pudo convertir certificado a PEM: {exc}") from exc

    return key_pem, cert_pem


def firmar_xml(xml_bytes: bytes) -> bytes:
    """Firma XML UBL 2.1 con XMLDSig enveloped e inserta ds:Signature en ExtensionContent."""
    private_key, certificate, _additional_certs = cargar_certificado_pfx()
    key_pem, cert_pem = convertir_certificado_a_pem(private_key, certificate)

    try:
        parser = etree.XMLParser(remove_blank_text=False)
        root = etree.fromstring(xml_bytes, parser=parser)
    except Exception as exc:
        raise FirmaDigitalError(f"XML invalido, no se pudo parsear: {exc}") from exc

    signer = XMLSigner(
        method=methods.enveloped,
        signature_algorithm="rsa-sha256",
        digest_algorithm="sha256",
        c14n_algorithm=CANONICALIZATION_ALGORITHM,
    )

    try:
        signed_root = signer.sign(root, key=key_pem, cert=cert_pem)
    except Exception as exc:
        raise FirmaDigitalError(f"No se pudo firmar el XML: {exc}") from exc

    signature = signed_root.find(f".//{{{NS_DS}}}Signature")
    if signature is None:
        raise FirmaDigitalError("No se genero ds:Signature.")

    signature.set("Id", "SignatureSP")
    parent = signature.getparent()
    if parent is not None:
        parent.remove(signature)

    extension_content = _obtener_o_crear_extension_content(signed_root)
    for existing in extension_content.findall(f"{{{NS_DS}}}Signature"):
        extension_content.remove(existing)
    extension_content.append(signature)

    xml_firmado = etree.tostring(
        signed_root,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
        standalone=False,
    )
    xml_firmado = limpiar_x509_certificate(xml_firmado)
    errores = validar_firma_basica(xml_firmado)
    if errores:
        raise FirmaDigitalError("XML firmado no pasa validacion basica: " + "; ".join(errores))
    return xml_firmado


def limpiar_x509_certificate(xml_firmado: bytes) -> bytes:
    """Elimina saltos de linea dentro de ds:X509Certificate."""
    text = xml_firmado.decode("utf-8")

    def repl(match):
        contenido = re.sub(r"\s+", "", match.group(1))
        return f"<ds:X509Certificate>{contenido}</ds:X509Certificate>"

    limpio = re.sub(
        r"<ds:X509Certificate>\s*(.*?)\s*</ds:X509Certificate>",
        repl,
        text,
        flags=re.DOTALL,
    )
    return limpio.encode("utf-8")


def validar_firma_basica(xml_firmado: bytes) -> list[str]:
    """Valida que la firma XMLDSig tenga los nodos mínimos esperados."""
    errores = []
    try:
        root = etree.fromstring(xml_firmado)
    except Exception as exc:
        return [f"XML firmado invalido: {exc}"]

    ns = {"ds": NS_DS, "ext": NS_EXT, "cbc": NS_CBC}
    signature = root.find(".//ds:Signature", namespaces=ns)
    if signature is None:
        errores.append("Falta ds:Signature.")
    else:
        extension_content = signature.getparent()
        if extension_content is None or extension_content.tag != f"{{{NS_EXT}}}ExtensionContent":
            errores.append("ds:Signature no esta dentro de ext:ExtensionContent.")

    required = {
        ".//ds:SignedInfo": "Falta ds:SignedInfo.",
        ".//ds:SignatureValue": "Falta ds:SignatureValue.",
        ".//ds:X509Certificate": "Falta ds:X509Certificate.",
        ".//ds:Reference": "Falta ds:Reference.",
        ".//ds:DigestValue": "Falta ds:DigestValue.",
    }
    for xpath, message in required.items():
        if root.find(xpath, namespaces=ns) is None:
            errores.append(message)

    ubl_version = root.find(".//cbc:UBLVersionID", namespaces=ns)
    if ubl_version is None:
        errores.append("Falta cbc:UBLVersionID.")
    elif (ubl_version.text or "").strip() != "2.1":
        errores.append("cbc:UBLVersionID debe ser 2.1.")

    customization = root.find(".//cbc:CustomizationID", namespaces=ns)
    if customization is None:
        errores.append("Falta cbc:CustomizationID.")
    elif (customization.text or "").strip() != "2.0":
        errores.append("cbc:CustomizationID debe ser 2.0.")

    return errores


def guardar_xml_firmado(comprobante, xml_firmado: bytes) -> str:
    """Guarda XML firmado en storage/xmls/firmados y actualiza el comprobante."""
    nombre = f"{nombre_archivo_sunat(comprobante)}.xml"
    destino = Path(settings.BASE_DIR) / "storage" / "xmls" / "firmados"
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / nombre
    ruta.write_bytes(xml_firmado)

    ruta_relativa = os.path.relpath(ruta, settings.BASE_DIR)
    update_fields = []
    if hasattr(comprobante, "xml_firmado"):
        comprobante.xml_firmado = ruta_relativa
        update_fields.append("xml_firmado")
    if hasattr(comprobante, "estado"):
        comprobante.estado = ESTADO_FIRMADO
        update_fields.append("estado")
    if update_fields:
        update_fields.append("actualizado_en")
        comprobante.save(update_fields=update_fields)
    return ruta_relativa


def generar_y_firmar_comprobante(comprobante) -> bytes:
    """Genera XML UBL, lo firma, valida la firma básica y guarda el XML firmado."""
    xml_bytes = generar_xml_comprobante(comprobante)
    xml_firmado = firmar_xml(xml_bytes)
    errores = validar_firma_basica(xml_firmado)
    if errores:
        raise FirmaDigitalError("XML firmado no pasa validacion basica: " + "; ".join(errores))
    guardar_xml_firmado(comprobante, xml_firmado)
    return xml_firmado


def _obtener_o_crear_extension_content(root):
    extension_content = root.find(f".//{{{NS_EXT}}}ExtensionContent")
    if extension_content is not None:
        return extension_content

    extensions = root.find(f".//{{{NS_EXT}}}UBLExtensions")
    if extensions is None:
        extensions = etree.Element(f"{{{NS_EXT}}}UBLExtensions")
        root.insert(0, extensions)

    extension = extensions.find(f"{{{NS_EXT}}}UBLExtension")
    if extension is None:
        extension = etree.SubElement(extensions, f"{{{NS_EXT}}}UBLExtension")

    extension_content = etree.SubElement(extension, f"{{{NS_EXT}}}ExtensionContent")
    if extension_content is None:
        raise FirmaDigitalError("No se pudo crear ext:ExtensionContent.")
    return extension_content
