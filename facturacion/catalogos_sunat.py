"""Códigos oficiales SUNAT usados en XML UBL (catálogos PE)."""

# Catálogo 07 - Tipo de afectación del IGV (cbc:TaxExemptionReasonCode)
AFECTACION_IGV_VALIDAS = frozenset({
    '10', '11', '12', '13', '14', '15', '16', '17',
    '20', '21', '30', '31', '32', '33', '34', '35', '36', '40',
})


def codigo_afectacion_igv(codigo: str | None) -> str:
    """
    Normaliza el código de afectación IGV para TaxExemptionReasonCode.

    En BD a veces se guardó '1000' (ID del tributo IGV en TaxScheme), pero SUNAT
    exige catálogo 07 (ej. '10' = gravado oneroso).
    """
    c = str(codigo or '10').strip()
    if c in AFECTACION_IGV_VALIDAS:
        return c
    # En líneas UBL el tributo IGV va en TaxScheme/cbc:ID=1000; TaxExemptionReasonCode es cat. 07.
    # Algunos XML antiguos guardaron 1000 en el campo de afectación — SUNAT beta exige cat. 07 (p. ej. 10).
    if c == '1000':
        return '10'
    if c.isdigit() and len(c) == 4 and c.startswith('10'):
        return '10'
    return '10'
