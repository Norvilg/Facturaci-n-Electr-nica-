from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from lxml import etree

from facturacion.constants import (
    AFECTACION_GRAVADO,
    IGV_RATE,
    MONEDA_PEN,
    TIPO_BOLETA,
    TIPO_FACTURA,
    TIPO_NOTA_CREDITO,
    TIPO_NOTA_DEBITO,
    TRIBUTO_IGV,
    UNIDAD_NIU,
)


NS_INVOICE = "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
NS_CREDIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2"
NS_DEBIT_NOTE = "urn:oasis:names:specification:ubl:schema:xsd:DebitNote-2"
NS_CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
NS_CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
NS_EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
NS_DS = "http://www.w3.org/2000/09/xmldsig#"

NSMAP_COMMON = {
    "cac": NS_CAC,
    "cbc": NS_CBC,
    "ext": NS_EXT,
    "ds": NS_DS,
}

CATALOGO_TIPO_OPERACION = "urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo17"
CATALOGO_TIPO_DOCUMENTO = "urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo01"
CATALOGO_IDENTIDAD = "urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo06"
CATALOGO_TIPO_PRECIO = "urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo16"
CATALOGO_AFECTACION_IGV = "urn:pe:gob:sunat:cpe:see:gem:catalogos:catalogo07"


def generar_xml_comprobante(comprobante) -> bytes:
    """Genera XML UBL 2.1 sin firma para factura, boleta, nota de credito o debito."""
    validar_comprobante_para_xml(comprobante)
    if comprobante.tipo_comprobante in {TIPO_FACTURA, TIPO_BOLETA}:
        return generar_xml_factura_boleta(comprobante)
    if comprobante.tipo_comprobante == TIPO_NOTA_CREDITO:
        return generar_xml_nota_credito(comprobante)
    if comprobante.tipo_comprobante == TIPO_NOTA_DEBITO:
        return generar_xml_nota_debito(comprobante)
    raise ValidationError(f"Tipo de comprobante no soportado: {comprobante.tipo_comprobante}")


def generar_xml_factura_boleta(comprobante) -> bytes:
    """Genera XML UBL 2.1 Invoice para factura 01 y boleta 03."""
    root = etree.Element(_q(NS_INVOICE, "Invoice"), nsmap={None: NS_INVOICE, **NSMAP_COMMON})
    _crear_ublextensions(root)
    _agregar_datos_comunes_invoice(root, comprobante)
    _agregar_signature(root, comprobante)
    _agregar_supplier(root, comprobante)
    _agregar_customer(root, comprobante)
    _agregar_payment_terms(root, comprobante)
    _agregar_tax_total(root, comprobante)
    _agregar_legal_monetary_total(root, comprobante)
    _agregar_invoice_lines(root, comprobante)
    return _serializar(root)


def generar_xml_nota_credito(comprobante) -> bytes:
    """Genera XML UBL 2.1 CreditNote para nota de credito 07."""
    root = etree.Element(
        _q(NS_CREDIT_NOTE, "CreditNote"),
        nsmap={None: NS_CREDIT_NOTE, **NSMAP_COMMON},
    )
    _crear_ublextensions(root)
    _agregar_datos_comunes_nota(root, comprobante)
    _agregar_discrepancy_response(root, comprobante)
    _agregar_billing_reference(root, comprobante)
    _agregar_signature(root, comprobante)
    _agregar_supplier(root, comprobante)
    _agregar_customer(root, comprobante)
    _agregar_tax_total(root, comprobante)
    _agregar_legal_monetary_total(root, comprobante)
    _agregar_note_lines(root, comprobante, line_tag="CreditNoteLine", quantity_tag="CreditedQuantity")
    return _serializar(root)


def generar_xml_nota_debito(comprobante) -> bytes:
    """Genera XML UBL 2.1 DebitNote para nota de debito 08."""
    root = etree.Element(
        _q(NS_DEBIT_NOTE, "DebitNote"),
        nsmap={None: NS_DEBIT_NOTE, **NSMAP_COMMON},
    )
    _crear_ublextensions(root)
    _agregar_datos_comunes_nota(root, comprobante)
    _agregar_discrepancy_response(root, comprobante)
    _agregar_billing_reference(root, comprobante)
    _agregar_signature(root, comprobante)
    _agregar_supplier(root, comprobante)
    _agregar_customer(root, comprobante)
    _agregar_tax_total(root, comprobante)
    _agregar_requested_monetary_total(root, comprobante)
    _agregar_note_lines(root, comprobante, line_tag="DebitNoteLine", quantity_tag="DebitedQuantity")
    return _serializar(root)


def nombre_archivo_sunat(comprobante) -> str:
    """Retorna RUC-TIPO-SERIE-NUMERO y valida consistencia con SUNAT_CERT_RUC."""
    sunat_ruc = getattr(settings, "SUNAT_CERT_RUC", "20100066603")
    if comprobante.empresa.ruc != sunat_ruc:
        raise ValidationError(
            f"RUC emisor {comprobante.empresa.ruc} no coincide con SUNAT_CERT_RUC {sunat_ruc}."
        )
    return f"{sunat_ruc}-{comprobante.tipo_comprobante}-{comprobante.serie.serie}-{comprobante.numero:08d}"


def guardar_xml_generado(comprobante, xml_bytes: bytes) -> str:
    """Guarda el XML sin firmar y retorna la ruta relativa.

    El modelo aun no tiene campo para XML sin firmar; en FASE 5 se persistira el XML firmado.
    """
    nombre = f"{nombre_archivo_sunat(comprobante)}.xml"
    destino = Path(settings.BASE_DIR) / "storage" / "xmls" / "generados"
    destino.mkdir(parents=True, exist_ok=True)
    ruta = destino / nombre
    ruta.write_bytes(xml_bytes)
    return str(ruta.relative_to(settings.BASE_DIR))


def validar_xml_basico(xml_bytes: bytes) -> list[str]:
    """Valida presencia de nodos mínimos del XML UBL generado."""
    errores = []
    root = etree.fromstring(xml_bytes)

    required = {
        "UBLVersionID": "Falta UBLVersionID.",
        "CustomizationID": "Falta CustomizationID.",
        "ID": "Falta ID.",
        "IssueDate": "Falta IssueDate.",
        "AccountingSupplierParty": "Falta AccountingSupplierParty.",
        "AccountingCustomerParty": "Falta AccountingCustomerParty.",
        "TaxTotal": "Falta TaxTotal.",
    }
    for local_name, mensaje in required.items():
        if not _exists(root, local_name):
            errores.append(mensaje)

    if not (_exists(root, "LegalMonetaryTotal") or _exists(root, "RequestedMonetaryTotal")):
        errores.append("Falta LegalMonetaryTotal o RequestedMonetaryTotal.")

    if not (
        _exists(root, "InvoiceLine")
        or _exists(root, "CreditNoteLine")
        or _exists(root, "DebitNoteLine")
    ):
        errores.append("Falta al menos una linea.")

    return errores


def validar_comprobante_para_xml(comprobante):
    if not comprobante:
        raise ValidationError("El comprobante es obligatorio.")
    if not comprobante.empresa_id:
        raise ValidationError("El comprobante debe tener empresa.")
    if not comprobante.cliente_id:
        raise ValidationError("El comprobante debe tener cliente.")
    if not comprobante.serie_id:
        raise ValidationError("El comprobante debe tener serie.")
    if comprobante.tipo_comprobante not in {
        TIPO_FACTURA,
        TIPO_BOLETA,
        TIPO_NOTA_CREDITO,
        TIPO_NOTA_DEBITO,
    }:
        raise ValidationError("Tipo de comprobante no soportado.")
    if comprobante.tipo_comprobante == TIPO_FACTURA and not comprobante.serie.serie.startswith("F"):
        raise ValidationError("La factura debe usar serie F.")
    if comprobante.tipo_comprobante == TIPO_BOLETA and not comprobante.serie.serie.startswith("B"):
        raise ValidationError("La boleta debe usar serie B.")
    if comprobante.tipo_comprobante in {TIPO_NOTA_CREDITO, TIPO_NOTA_DEBITO}:
        if not comprobante.comprobante_referencia_id:
            raise ValidationError("La nota debe tener comprobante de referencia.")
    if not comprobante.detalles.exists():
        raise ValidationError("El comprobante debe tener detalles.")
    for field in ("subtotal", "igv", "total", "descuento_total"):
        if Decimal(getattr(comprobante, field) or "0") < 0:
            raise ValidationError(f"El campo {field} no puede ser negativo.")
    if comprobante.empresa.ruc != getattr(settings, "SUNAT_CERT_RUC", "20100066603"):
        raise ValidationError("El RUC de la empresa debe coincidir con SUNAT_CERT_RUC.")


def _fmt_decimal(valor, decimales=2) -> str:
    quant = Decimal("1").scaleb(-decimales)
    return str(Decimal(valor or "0").quantize(quant, rounding=ROUND_HALF_UP))


def _q(namespace: str, tag: str) -> str:
    return f"{{{namespace}}}{tag}"


def _sub(parent, namespace: str, tag: str, text=None, **attrs):
    element = etree.SubElement(parent, _q(namespace, tag), **{k: str(v) for k, v in attrs.items()})
    if text is not None:
        element.text = str(text)
    return element


def _cbc(parent, tag: str, text=None, **attrs):
    return _sub(parent, NS_CBC, tag, text, **attrs)


def _cac(parent, tag: str, text=None, **attrs):
    return _sub(parent, NS_CAC, tag, text, **attrs)


def _ext(parent, tag: str, text=None, **attrs):
    return _sub(parent, NS_EXT, tag, text, **attrs)


def _crear_ublextensions(root):
    extensions = _ext(root, "UBLExtensions")
    extension = _ext(extensions, "UBLExtension")
    # FASE 5 insertara ds:Signature dentro de ExtensionContent.
    _ext(extension, "ExtensionContent")


def _agregar_datos_comunes_invoice(root, comprobante):
    _cbc(root, "UBLVersionID", "2.1")
    _cbc(root, "CustomizationID", "2.0")
    _cbc(
        root,
        "ProfileID",
        "0101",
        schemeName="SUNAT:Identificador de Tipo de Operacion",
        schemeAgencyName="PE:SUNAT",
        schemeURI=CATALOGO_TIPO_OPERACION,
    )
    _cbc(root, "ID", comprobante.numero_formateado())
    _cbc(root, "IssueDate", comprobante.fecha_emision.isoformat())
    _cbc(root, "IssueTime", comprobante.hora_emision.strftime("%H:%M:%S"))
    _cbc(
        root,
        "InvoiceTypeCode",
        comprobante.tipo_comprobante,
        listAgencyName="PE:SUNAT",
        listName="SUNAT:Identificador de Tipo de Documento",
        listURI=CATALOGO_TIPO_DOCUMENTO,
    )
    _agregar_moneda(root, comprobante.moneda)
    _cbc(root, "LineCountNumeric", str(comprobante.detalles.count()))
    # cbc:Note se mantiene desactivado por defecto; algunas respuestas Beta
    # rechazan leyendas con languageLocaleID cuando el XML aun no esta completo.


def _agregar_datos_comunes_nota(root, comprobante):
    _cbc(root, "UBLVersionID", "2.1")
    _cbc(root, "CustomizationID", "2.0")
    _cbc(root, "ID", comprobante.numero_formateado())
    _cbc(root, "IssueDate", comprobante.fecha_emision.isoformat())
    _cbc(root, "IssueTime", comprobante.hora_emision.strftime("%H:%M:%S"))
    _agregar_moneda(root, comprobante.moneda)


def _agregar_moneda(root, moneda):
    _cbc(
        root,
        "DocumentCurrencyCode",
        moneda or MONEDA_PEN,
        listID="ISO 4217 Alpha",
        listName="Currency",
        listAgencyName="United Nations Economic Commission for Europe",
    )


def _agregar_signature(root, comprobante):
    signature = _cac(root, "Signature")
    _cbc(signature, "ID", "SignatureSP")
    signatory = _cac(signature, "SignatoryParty")
    party_id = _cac(signatory, "PartyIdentification")
    _cbc(party_id, "ID", comprobante.empresa.ruc)
    party_name = _cac(signatory, "PartyName")
    _cbc(party_name, "Name", comprobante.empresa.razon_social)
    attachment = _cac(signature, "DigitalSignatureAttachment")
    reference = _cac(attachment, "ExternalReference")
    _cbc(reference, "URI", "#SignatureSP")


def _agregar_supplier(root, comprobante):
    supplier = _cac(root, "AccountingSupplierParty")
    party = _cac(supplier, "Party")
    party_name = _cac(party, "PartyName")
    _cbc(party_name, "Name", comprobante.empresa.nombre_comercial or comprobante.empresa.razon_social)

    tax_scheme = _cac(party, "PartyTaxScheme")
    _cbc(tax_scheme, "RegistrationName", comprobante.empresa.razon_social)
    _company_id(tax_scheme, comprobante.empresa.ruc, "6")
    tax = _cac(tax_scheme, "TaxScheme")
    _cbc(tax, "ID", "-")

    legal = _cac(party, "PartyLegalEntity")
    _cbc(legal, "RegistrationName", comprobante.empresa.razon_social)
    address = _cac(legal, "RegistrationAddress")
    _cbc(address, "ID", comprobante.empresa.ubigeo)
    _cbc(address, "AddressTypeCode", "0000")
    _cbc(address, "CityName", comprobante.empresa.provincia)
    _cbc(address, "CountrySubentity", comprobante.empresa.departamento)
    _cbc(address, "District", comprobante.empresa.distrito)
    line = _cac(address, "AddressLine")
    _cbc(line, "Line", comprobante.empresa.direccion)
    country = _cac(address, "Country")
    _cbc(country, "IdentificationCode", "PE")


def _agregar_customer(root, comprobante):
    customer = _cac(root, "AccountingCustomerParty")
    party = _cac(customer, "Party")
    identification = _cac(party, "PartyIdentification")
    _cbc(identification, "ID", comprobante.cliente.numero_documento, schemeID=comprobante.cliente.tipo_documento)

    tax_scheme = _cac(party, "PartyTaxScheme")
    _cbc(tax_scheme, "RegistrationName", comprobante.cliente.razon_social)
    _company_id(tax_scheme, comprobante.cliente.numero_documento, comprobante.cliente.tipo_documento)
    tax = _cac(tax_scheme, "TaxScheme")
    _cbc(tax, "ID", "-")

    legal = _cac(party, "PartyLegalEntity")
    _cbc(legal, "RegistrationName", comprobante.cliente.razon_social)
    if comprobante.cliente.direccion:
        address = _cac(legal, "RegistrationAddress")
        line = _cac(address, "AddressLine")
        _cbc(line, "Line", comprobante.cliente.direccion)
        country = _cac(address, "Country")
        _cbc(country, "IdentificationCode", "PE")


def _company_id(parent, numero_documento, scheme_id):
    _cbc(
        parent,
        "CompanyID",
        numero_documento,
        schemeID=scheme_id,
        schemeName="SUNAT:Identificador de Documento de Identidad",
        schemeAgencyName="PE:SUNAT",
        schemeURI=CATALOGO_IDENTIDAD,
    )


def _agregar_payment_terms(root, comprobante):
    payment = _cac(root, "PaymentTerms")
    _cbc(payment, "ID", "FormaPago")
    _cbc(payment, "PaymentMeansID", comprobante.forma_pago or "Contado")


def _agregar_tax_total(root, comprobante):
    tax_total = _cac(root, "TaxTotal")
    _cbc(tax_total, "TaxAmount", _fmt_decimal(comprobante.igv), currencyID=comprobante.moneda)
    subtotal = _cac(tax_total, "TaxSubtotal")
    _cbc(subtotal, "TaxableAmount", _fmt_decimal(comprobante.subtotal), currencyID=comprobante.moneda)
    _cbc(subtotal, "TaxAmount", _fmt_decimal(comprobante.igv), currencyID=comprobante.moneda)
    category = _cac(subtotal, "TaxCategory")
    _cbc(category, "ID", "S")
    _tax_scheme(category)


def _tax_scheme(parent):
    scheme = _cac(parent, "TaxScheme")
    _cbc(scheme, "ID", TRIBUTO_IGV, schemeID="UN/ECE 5153", schemeAgencyID="6")
    _cbc(scheme, "Name", "IGV")
    _cbc(scheme, "TaxTypeCode", "VAT")


def _tax_scheme_line(parent):
    scheme = _cac(parent, "TaxScheme")
    _cbc(
        scheme,
        "ID",
        TRIBUTO_IGV,
        schemeID="UN/ECE 5153",
        schemeName="Tax Scheme Identifier",
        schemeAgencyName="United Nations Economic Commission for Europe",
    )
    _cbc(scheme, "Name", "IGV")
    _cbc(scheme, "TaxTypeCode", "VAT")


def _agregar_legal_monetary_total(root, comprobante):
    total = _cac(root, "LegalMonetaryTotal")
    _monetary_total_fields(total, comprobante)


def _agregar_requested_monetary_total(root, comprobante):
    total = _cac(root, "RequestedMonetaryTotal")
    _monetary_total_fields(total, comprobante)


def _monetary_total_fields(parent, comprobante):
    _cbc(parent, "LineExtensionAmount", _fmt_decimal(comprobante.subtotal), currencyID=comprobante.moneda)
    _cbc(parent, "TaxExclusiveAmount", _fmt_decimal(comprobante.subtotal), currencyID=comprobante.moneda)
    _cbc(parent, "TaxInclusiveAmount", _fmt_decimal(comprobante.total), currencyID=comprobante.moneda)
    _cbc(parent, "PayableAmount", _fmt_decimal(comprobante.total), currencyID=comprobante.moneda)


def _agregar_invoice_lines(root, comprobante):
    for index, detalle in enumerate(comprobante.detalles.select_related("producto").all(), start=1):
        line = _cac(root, "InvoiceLine")
        _agregar_linea_comun(line, detalle, index, comprobante.moneda, quantity_tag="InvoicedQuantity")


def _agregar_note_lines(root, comprobante, *, line_tag: str, quantity_tag: str):
    for index, detalle in enumerate(comprobante.detalles.select_related("producto").all(), start=1):
        line = _cac(root, line_tag)
        _agregar_linea_comun(line, detalle, index, comprobante.moneda, quantity_tag=quantity_tag)


def _agregar_linea_comun(line, detalle, index: int, moneda: str, *, quantity_tag: str):
    _cbc(line, "ID", str(index))
    _cbc(
        line,
        quantity_tag,
        _fmt_decimal(detalle.cantidad),
        unitCode=detalle.unidad_medida or UNIDAD_NIU,
    )
    _cbc(line, "LineExtensionAmount", _fmt_decimal(detalle.subtotal), currencyID=moneda)
    pricing = _cac(line, "PricingReference")
    alternative = _cac(pricing, "AlternativeConditionPrice")
    _cbc(alternative, "PriceAmount", _fmt_decimal(_precio_con_igv(detalle)), currencyID=moneda)
    _cbc(
        alternative,
        "PriceTypeCode",
        "01",
        listName="SUNAT:Indicador de Tipo de Precio",
        listAgencyName="PE:SUNAT",
        listURI=CATALOGO_TIPO_PRECIO,
    )
    _agregar_tax_total_linea(line, detalle, moneda)
    _agregar_item(line, detalle)
    price = _cac(line, "Price")
    _cbc(price, "PriceAmount", _fmt_decimal(detalle.precio_unitario), currencyID=moneda)


def _precio_con_igv(detalle) -> Decimal:
    if detalle.cantidad == 0:
        return Decimal("0.00")
    return Decimal(detalle.total_linea) / Decimal(detalle.cantidad)


def _agregar_tax_total_linea(line, detalle, moneda):
    tax_total = _cac(line, "TaxTotal")
    _cbc(tax_total, "TaxAmount", _fmt_decimal(detalle.igv_linea), currencyID=moneda)
    subtotal = _cac(tax_total, "TaxSubtotal")
    _cbc(subtotal, "TaxableAmount", _fmt_decimal(detalle.subtotal), currencyID=moneda)
    _cbc(subtotal, "TaxAmount", _fmt_decimal(detalle.igv_linea), currencyID=moneda)
    category = _cac(subtotal, "TaxCategory")
    _cbc(
        category,
        "ID",
        "S",
        schemeID="UN/ECE 5305",
        schemeName="Tax Category Identifier",
        schemeAgencyName="United Nations Economic Commission for Europe",
    )
    _cbc(category, "Percent", "18.00")
    _cbc(
        category,
        "TaxExemptionReasonCode",
        detalle.codigo_afectacion_igv or AFECTACION_GRAVADO,
        listAgencyName="PE:SUNAT",
        listName="SUNAT:Codigo de Tipo de Afectacion del IGV",
        listURI=CATALOGO_AFECTACION_IGV,
    )
    _tax_scheme_line(category)


def _agregar_item(line, detalle):
    item = _cac(line, "Item")
    _cbc(item, "Description", detalle.descripcion)
    seller = _cac(item, "SellersItemIdentification")
    _cbc(seller, "ID", detalle.producto.codigo)
    commodity = _cac(item, "CommodityClassification")
    _cbc(
        commodity,
        "ItemClassificationCode",
        detalle.producto.codigo_sunat_unspsc,
        listID="UNSPSC",
        listAgencyName="GS1 US",
        listName="Item Classification",
    )


def _agregar_discrepancy_response(root, comprobante):
    reference = comprobante.comprobante_referencia
    response = _cac(root, "DiscrepancyResponse")
    _cbc(response, "ReferenceID", reference.numero_formateado())
    _cbc(response, "ResponseCode", comprobante.tipo_nota)
    _cbc(response, "Description", comprobante.motivo_nota)


def _agregar_billing_reference(root, comprobante):
    reference = comprobante.comprobante_referencia
    billing = _cac(root, "BillingReference")
    invoice_reference = _cac(billing, "InvoiceDocumentReference")
    _cbc(invoice_reference, "ID", reference.numero_formateado())
    _cbc(invoice_reference, "DocumentTypeCode", reference.tipo_comprobante)


def _serializar(root) -> bytes:
    return etree.tostring(
        root,
        encoding="UTF-8",
        xml_declaration=True,
        pretty_print=True,
        standalone=False,
    )


def _exists(root, local_name: str) -> bool:
    return bool(root.xpath(f".//*[local-name()=$name]", name=local_name))
