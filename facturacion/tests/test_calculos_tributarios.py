"""
Tests de cálculo tributario (IGV 18%) — rúbrica docente.
"""
from decimal import Decimal
from django.test import SimpleTestCase

from facturacion.calculos_tributarios import (
    IGV_TASA,
    calcular_linea_detalle,
    calcular_totales_desde_total_con_igv,
    sumar_totales_lineas,
)


class CalculoLineaDetalleTests(SimpleTestCase):
    def test_igv_18_por_ciento_sobre_base(self):
        linea = calcular_linea_detalle(2, '50.00')
        self.assertEqual(linea['valor_total'], Decimal('100.00'))
        self.assertEqual(linea['igv'], Decimal('18.00'))
        self.assertEqual(linea['importe_total'], Decimal('118.00'))

    def test_precio_unitario_con_igv(self):
        linea = calcular_linea_detalle(1, '10.00')
        self.assertEqual(linea['precio_unitario'], Decimal('11.80'))

    def test_porcentaje_igv_registrado(self):
        linea = calcular_linea_detalle(1, '100')
        self.assertEqual(linea['porcentaje_igv'], IGV_TASA)


class CalculoTotalesNotaCreditoTests(SimpleTestCase):
    def test_descomposicion_11_80(self):
        t = calcular_totales_desde_total_con_igv('11.80')
        self.assertEqual(t['op_grabadas'], Decimal('10.00'))
        self.assertEqual(t['igv'], Decimal('1.80'))
        self.assertEqual(t['total'], Decimal('11.80'))

    def test_monto_cero_rechazado(self):
        with self.assertRaises(ValueError):
            calcular_totales_desde_total_con_igv(0)


class SumaLineasTests(SimpleTestCase):
    def test_suma_dos_productos(self):
        l1 = calcular_linea_detalle(1, '5')
        l2 = calcular_linea_detalle(1, '5')
        tot = sumar_totales_lineas([l1, l2])
        self.assertEqual(tot['op_grabadas'], Decimal('10.00'))
        self.assertEqual(tot['igv'], Decimal('1.80'))
        self.assertEqual(tot['total'], Decimal('11.80'))
