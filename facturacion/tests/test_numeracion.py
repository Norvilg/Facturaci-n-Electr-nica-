"""
Tests de numeración correlativa — rúbrica docente.
"""
from django.test import TestCase, TransactionTestCase
from django.db import transaction

from facturacion.models import Serie, TipoComprobante
from facturacion.numeracion import (
    formato_numeracion,
    nombre_archivo_sunat,
    siguiente_correlativo,
)


class NumeracionFormatoTests(TestCase):
    def test_formato_numeracion_ocho_digitos(self):
        self.assertEqual(formato_numeracion('F001', 68), 'F001-00000068')

    def test_nombre_archivo_sunat(self):
        nombre = nombre_archivo_sunat('20123456789', '01', 'F001', 12)
        self.assertEqual(nombre, '20123456789-01-F001-00000012')


class SiguienteCorrelativoTests(TransactionTestCase):
    def setUp(self):
        tipo = TipoComprobante.objects.create(descripcion='Factura')
        self.serie = Serie.objects.create(serie='T999', correlativo=10, id_tipo_comprobante=tipo)

    def test_incrementa_y_persiste(self):
        with transaction.atomic():
            nuevo = siguiente_correlativo(self.serie)
        self.assertEqual(nuevo, 11)
        self.serie.refresh_from_db()
        self.assertEqual(self.serie.correlativo, 11)

    def test_llamadas_secuenciales(self):
        with transaction.atomic():
            a = siguiente_correlativo(self.serie)
            self.serie.refresh_from_db()
            b = siguiente_correlativo(self.serie)
        self.assertEqual(a, 11)
        self.assertEqual(b, 12)
