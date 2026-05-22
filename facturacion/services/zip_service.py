import io
import os
import re
import zipfile
from pathlib import Path

from django.conf import settings

from facturacion.constants import (
    TIPO_BOLETA,
    TIPO_FACTURA,
    TIPO_NOTA_CREDITO,
    TIPO_NOTA_DEBITO,
)
from facturacion.services.xml_builder import nombre_archivo_sunat
from facturacion.services.xml_signer import generar_y_firmar_comprobante


TIPOS_PERMITIDOS = {TIPO_FACTURA, TIPO_BOLETA, TIPO_NOTA_CREDITO, TIPO_NOTA_DEBITO}
NOMBRE_SUNAT_RE = re.compile(r"^(?P<ruc>\d{11})-(?P<tipo>\d{2})-(?P<serie>[A-Z0-9]{4})-(?P<num>\d{8})$")


class ZipSunatError(Exception):
    pass


def crear_zip_sunat(nombre_archivo: str, xml_firmado: bytes) -> bytes:
    """Crea en memoria el ZIP SUNAT con un único XML firmado."""
    _validar_nombre_archivo(nombre_archivo)
    if not xml_firmado:
        raise ZipSunatError("XML firmado vacío.")

    buffer = io.BytesIO()
    try:
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(f"{nombre_archivo}.xml", xml_firmado)
    except Exception as exc:
        raise ZipSunatError(f"No se pudo crear ZIP SUNAT: {exc}") from exc

    zip_bytes = buffer.getvalue()
    errores = validar_zip_sunat(zip_bytes, nombre_archivo)
    if errores:
        raise ZipSunatError("ZIP SUNAT inválido: " + "; ".join(errores))
    return zip_bytes


def guardar_zip_sunat(comprobante, zip_bytes: bytes) -> str:
    """Guarda el ZIP SUNAT en storage/xmls/firmados y actualiza comprobante.zip_enviado."""
    if not zip_bytes:
        raise ZipSunatError("ZIP vacío.")

    nombre = nombre_archivo_sunat(comprobante)
    destino = Path(settings.BASE_DIR) / "storage" / "xmls" / "firmados"
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / f"{nombre}.zip"
    ruta.write_bytes(zip_bytes)

    ruta_relativa = os.path.relpath(ruta, settings.BASE_DIR)
    if hasattr(comprobante, "zip_enviado"):
        comprobante.zip_enviado = ruta_relativa
        comprobante.save(update_fields=["zip_enviado", "actualizado_en"])
    return ruta_relativa


def validar_zip_sunat(zip_bytes: bytes, nombre_archivo: str) -> list[str]:
    """Valida que el ZIP tenga exactamente nombre_archivo.xml en la raíz."""
    errores = []
    try:
        _validar_nombre_archivo(nombre_archivo)
    except ZipSunatError as exc:
        errores.append(str(exc))
        return errores

    if not zip_bytes:
        return ["ZIP vacío."]

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes), mode="r") as zip_file:
            nombres = zip_file.namelist()
            if len(nombres) != 1:
                errores.append("ZIP debe contener exactamente 1 archivo.")
                return errores

            nombre_interno = nombres[0]
            esperado = f"{nombre_archivo}.xml"
            if nombre_interno != esperado:
                errores.append(f"Nombre interno inválido: {nombre_interno}. Esperado: {esperado}.")
            if "/" in nombre_interno or "\\" in nombre_interno:
                errores.append("ZIP no debe contener carpetas internas.")

            contenido = zip_file.read(nombre_interno)
            if not contenido:
                errores.append("XML interno vacío.")
            elif not contenido.lstrip().startswith(b"<?xml"):
                errores.append("XML interno no empieza con declaración XML.")
    except zipfile.BadZipFile:
        errores.append("ZIP no se puede abrir.")
    except Exception as exc:
        errores.append(f"No se pudo validar ZIP: {exc}")

    return errores


def generar_zip_para_comprobante(comprobante) -> bytes:
    """Obtiene o genera XML firmado, crea ZIP SUNAT, valida y guarda el ZIP."""
    nombre = nombre_archivo_sunat(comprobante)
    xml_firmado = leer_xml_firmado_desde_comprobante(comprobante)
    if not xml_firmado:
        xml_firmado = generar_y_firmar_comprobante(comprobante)

    zip_bytes = crear_zip_sunat(nombre, xml_firmado)
    errores = validar_zip_sunat(zip_bytes, nombre)
    if errores:
        raise ZipSunatError("ZIP SUNAT inválido: " + "; ".join(errores))
    guardar_zip_sunat(comprobante, zip_bytes)
    return zip_bytes


def leer_xml_firmado_desde_comprobante(comprobante) -> bytes | None:
    """Lee el XML firmado configurado en comprobante.xml_firmado si existe."""
    ruta_guardada = getattr(comprobante, "xml_firmado", "")
    if not ruta_guardada:
        return None

    ruta = Path(ruta_guardada)
    if not ruta.is_absolute():
        ruta = Path(settings.BASE_DIR) / ruta
    ruta = ruta.resolve()

    base_dir = Path(settings.BASE_DIR).resolve()
    try:
        ruta.relative_to(base_dir)
    except ValueError as exc:
        raise ZipSunatError("Ruta de XML firmado fuera del proyecto.") from exc

    if not ruta.exists():
        raise ZipSunatError(f"No existe XML firmado en disco: {ruta}")
    if not ruta.is_file():
        raise ZipSunatError(f"La ruta de XML firmado no es un archivo: {ruta}")

    return ruta.read_bytes()


def _validar_nombre_archivo(nombre_archivo: str):
    if not nombre_archivo:
        raise ZipSunatError("Nombre SUNAT vacío.")

    match = NOMBRE_SUNAT_RE.match(nombre_archivo)
    if not match:
        raise ZipSunatError("Nombre SUNAT inválido. Formato requerido: RUC-TIPO-SERIE-NUMERO.")

    sunat_ruc = getattr(settings, "SUNAT_CERT_RUC", "20100066603")
    if match.group("ruc") != sunat_ruc:
        raise ZipSunatError(f"RUC {match.group('ruc')} no coincide con SUNAT_CERT_RUC {sunat_ruc}.")

    if match.group("tipo") not in TIPOS_PERMITIDOS:
        raise ZipSunatError("Tipo de comprobante no permitido para ZIP SUNAT.")
