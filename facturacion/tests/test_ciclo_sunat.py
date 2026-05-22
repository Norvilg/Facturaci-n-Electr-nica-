"""
Tests del ciclo SUNAT (XML → envío → CDR) — rúbrica docente.
"""
import os
import tempfile
import zipfile
from decimal import Decimal
from datetime import date
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings

from facturacion.generarXmlFirmar import enviar_a_sunat, generar_xml_y_firmar
from facturacion.services_sunat import (
    ComprobanteProxy,
    ClienteProxy,
    DetalleProxy,
    EmpresaProxy,
    ProductoProxy,
    SerieProxy,
)
from facturacion.services_sunat_conexion import enviar_xml_zipeado


def _proxy_minimo():
    producto = ProductoProxy('SERVICIO', 'NIU', '10')
    detalle = DetalleProxy(
        producto=producto,
        descripcion='SERVICIO',
        cantidad=Decimal('1'),
        unidad_medida='NIU',
        precio_unitario=Decimal('10.00'),
        descuento=Decimal('0'),
        igv_linea=Decimal('1.80'),
        subtotal=Decimal('10.00'),
        total=Decimal('11.80'),
    )
    return ComprobanteProxy(
        empresa=EmpresaProxy('20123456789', 'EMPRESA TEST SAC', 'LIMA'),
        serie=SerieProxy('F001'),
        cliente=ClienteProxy('10459336635', '6', 'CLIENTE TEST', 'LIMA'),
        tipo='01',
        numero=99,
        fecha_emision=date(2026, 5, 21),
        moneda='PEN',
        subtotal=Decimal('10.00'),
        igv=Decimal('1.80'),
        total=Decimal('11.80'),
        _detalles=[detalle],
    )


class EnvioSunatSimuladoTests(TestCase):
    def test_enviar_xml_zipeado_aceptado_genera_cdr(self):
        with tempfile.TemporaryDirectory() as tmp:
            cdr_dir = os.path.join(tmp, 'storage', 'xmls', 'cdrs')
            with self.settings(
                BASE_DIR=tmp,
                CDRS_DIR=cdr_dir,
                SUNAT_MODO='simulado',
            ):
                resultado = enviar_xml_zipeado('20123456789-01-F001-00000099')
                self.assertEqual(resultado['identificador'], 'ACEPTADO')
                self.assertEqual(resultado['codigo'], '0')
                cdr_path = os.path.join(
                    cdr_dir, 'R-20123456789-01-F001-00000099.xml'
                )
                self.assertTrue(os.path.isfile(cdr_path))
                with open(cdr_path, encoding='utf-8') as f:
                    contenido = f.read()
                self.assertIn('ApplicationResponse', contenido)
                self.assertIn('ResponseCode', contenido)
                self.assertIn('>0<', contenido)

    @override_settings(SUNAT_MODO='simulado')
    def test_modo_simulado_sin_xml(self):
        resultado = enviar_xml_zipeado('20123456789-01-F001-00000001')
        self.assertEqual(resultado['identificador'], 'ACEPTADO')


class EnvioSunatBetaTests(TestCase):
    @patch('facturacion.services_sunat_conexion.requests.post')
    @override_settings(SUNAT_MODO='beta')
    def test_modo_beta_usa_soap(self, mock_post):
        cdr_xml = (
            '<?xml version="1.0"?>'
            '<ApplicationResponse xmlns="urn:oasis:names:specification:ubl:schema:xsd:ApplicationResponse-2"'
            ' xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"'
            ' xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">'
            '<cac:DocumentResponse><cac:Response>'
            '<cbc:ResponseCode>0</cbc:ResponseCode>'
            '<cbc:Description>OK</cbc:Description>'
            '</cac:Response></cac:DocumentResponse></ApplicationResponse>'
        )
        import io
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, 'w') as zf:
            zf.writestr('R-20123456789-01-F001-00000088.xml', cdr_xml)
        cdr_b64 = __import__('base64').b64encode(zip_buf.getvalue()).decode()

        soap_resp = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">'
            '<soapenv:Body><applicationResponse>'
            f'{cdr_b64}</applicationResponse></soapenv:Body></soapenv:Envelope>'
        )
        mock_post.return_value.status_code = 200
        mock_post.return_value.content = soap_resp.encode()

        with tempfile.TemporaryDirectory() as tmp:
            xml_dir = os.path.join(tmp, 'storage', 'xmls', 'firmados')
            cdr_dir = os.path.join(tmp, 'storage', 'xmls', 'cdrs')
            os.makedirs(xml_dir, exist_ok=True)
            with self.settings(
                BASE_DIR=tmp,
                XML_FIRMADOS_DIR=xml_dir,
                CDRS_DIR=cdr_dir,
            ):
                xml = b'<?xml version="1.0"?><Invoice/>'
                resultado = enviar_xml_zipeado('20123456789-01-F001-00000088', xml)
        self.assertEqual(resultado['identificador'], 'ACEPTADO')
        mock_post.assert_called_once()
        self.assertEqual(resultado['cdr_file'], 'R-20123456789-01-F001-00000088.xml')


class GenerarXmlTests(TestCase):
    @patch('facturacion.generarXmlFirmar._firmar_xml')
    def test_generar_xml_contiene_ubl_21(self, mock_firma):
        mock_firma.side_effect = lambda xml: xml.encode('utf-8')
        proxy = _proxy_minimo()
        xml_bytes = generar_xml_y_firmar(proxy)
        xml = xml_bytes.decode('utf-8')
        self.assertIn('UBLVersionID', xml)
        self.assertIn('2.1', xml)
        self.assertIn('InvoiceTypeCode', xml)
        self.assertIn('F001-00000099', xml)


class CicloCompletoSunatTests(TestCase):
    @patch('facturacion.generarXmlFirmar._firmar_xml')
    @patch('facturacion.generarXmlFirmar.enviar_xml_zipeado')
    def test_enviar_a_sunat_flujo_aceptado(self, mock_envio, mock_firma):
        mock_firma.side_effect = lambda xml: xml.encode('utf-8')
        mock_envio.return_value = {
            'identificador': 'ACEPTADO',
            'codigo': '0',
            'mensaje': 'Aceptado simulado',
            'cdr_file': 'R-test.xml',
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(BASE_DIR=tmp, SUNAT_MODO='simulado'):
                proxy = _proxy_minimo()
                resultado = enviar_a_sunat(proxy)
        self.assertEqual(resultado['estado'], 'ACEPTADO')
        self.assertEqual(resultado['codigo'], '0')
        self.assertTrue(proxy.xml_firmado.endswith('.xml'))

    @patch('facturacion.generarXmlFirmar._firmar_xml')
    @patch('facturacion.generarXmlFirmar.enviar_xml_zipeado')
    def test_enviar_a_sunat_rechazado(self, mock_envio, mock_firma):
        mock_firma.side_effect = lambda xml: xml.encode('utf-8')
        mock_envio.return_value = {
            'identificador': 'ERROR',
            'codigo': '9999',
            'mensaje': 'Error simulado',
        }
        with tempfile.TemporaryDirectory() as tmp:
            with self.settings(BASE_DIR=tmp, SUNAT_MODO='simulado'):
                resultado = enviar_a_sunat(_proxy_minimo())
        self.assertEqual(resultado['estado'], 'RECHAZADO')
