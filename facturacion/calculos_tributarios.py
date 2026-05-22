"""
Cálculos tributarios (IGV 18%) — módulo testeable para la rúbrica del docente.
"""
from decimal import Decimal

IGV_TASA = Decimal('0.18')
IGV_FACTOR = Decimal('1.18')


def calcular_linea_detalle(cantidad, valor_unitario_sin_igv) -> dict:
    """
    Calcula una línea de detalle gravada con IGV 18%.

    Parámetros
    ----------
    cantidad : cantidad vendida
    valor_unitario_sin_igv : precio unitario sin IGV (base imponible unitaria)
    """
    cantidad = Decimal(str(cantidad))
    v_unitario = Decimal(str(valor_unitario_sin_igv))

    valor_total = (cantidad * v_unitario).quantize(Decimal('0.01'))
    igv_linea = (valor_total * IGV_TASA).quantize(Decimal('0.01'))
    precio_unit = (v_unitario * IGV_FACTOR).quantize(Decimal('0.01'))
    importe_total = (valor_total + igv_linea).quantize(Decimal('0.01'))

    return {
        'valor_unitario': v_unitario,
        'precio_unitario': precio_unit,
        'valor_total': valor_total,
        'igv': igv_linea,
        'porcentaje_igv': IGV_TASA,
        'importe_total': importe_total,
    }


def calcular_totales_desde_total_con_igv(total_con_igv) -> dict:
    """Descompone un monto con IGV incluido en base + IGV."""
    total = Decimal(str(total_con_igv)).quantize(Decimal('0.01'))
    if total <= 0:
        raise ValueError('El monto debe ser mayor a cero.')
    op_grabadas = (total / IGV_FACTOR).quantize(Decimal('0.01'))
    igv = (total - op_grabadas).quantize(Decimal('0.01'))
    return {
        'op_grabadas': op_grabadas,
        'igv': igv,
        'total': total,
    }


def sumar_totales_lineas(lineas: list[dict]) -> dict:
    """Suma bases e IGV de varias líneas ya calculadas."""
    op = Decimal('0')
    igv = Decimal('0')
    for linea in lineas:
        op += Decimal(str(linea['valor_total']))
        igv += Decimal(str(linea['igv']))
    op = op.quantize(Decimal('0.01'))
    igv = igv.quantize(Decimal('0.01'))
    return {
        'op_grabadas': op,
        'igv': igv,
        'total': (op + igv).quantize(Decimal('0.01')),
    }
