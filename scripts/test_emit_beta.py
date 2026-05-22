"""Genera XML con generarXmlFirmar y envía a SUNAT beta (prueba manual)."""
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import django

BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from facturacion.generarXmlFirmar import enviar_xml_zipeado, generar_xml_y_firmar
from facturacion.services_sunat import (
    ClienteProxy,
    ComprobanteProxy,
    DetalleProxy,
    EmpresaProxy,
    ProductoProxy,
    SerieProxy,
)

numero = int(sys.argv[1]) if len(sys.argv) > 1 else 74
ruc = sys.argv[2] if len(sys.argv) > 2 else '20100066603'
proxy = ComprobanteProxy(
    empresa=EmpresaProxy(ruc, 'TU EMPRESA S.A.', 'AV. PRINCIPAL 123 - LIMA'),
    serie=SerieProxy('F001'),
    cliente=ClienteProxy('10456789', '1', 'JUAN PEREZ GARCIA', 'URB. LOS CLAVELES MZ. B LT. 12 - TRUJILLO'),
    tipo='01',
    numero=numero,
    fecha_emision=date.today(),
    moneda='PEN',
    subtotal=Decimal('85.00'),
    igv=Decimal('15.30'),
    total=Decimal('100.30'),
    _detalles=[
        DetalleProxy(
            producto=ProductoProxy('Licencia Office 365 (1 año)', 'NIU', '10'),
            descripcion='Licencia Office 365 (1 año)',
            cantidad=Decimal('1'),
            unidad_medida='NIU',
            precio_unitario=Decimal('85.00'),
            descuento=Decimal('0'),
            igv_linea=Decimal('15.30'),
            subtotal=Decimal('85.00'),
            total=Decimal('100.30'),
        ),
    ],
)

nombre = proxy.nombre_archivo_sunat()
print('Generando y firmando', nombre)
xml_bytes = generar_xml_y_firmar(proxy)
firmado = BASE / 'storage' / 'xmls' / 'firmados' / f'{nombre}.xml'
firmado.write_bytes(xml_bytes)
print('Guardado:', firmado, '| bytes:', len(xml_bytes))
print('KeyInfo cert:', b'X509Certificate' in xml_bytes)

resultado = enviar_xml_zipeado(
    nombre,
    xml_bytes,
    credenciales={
        'ruc': ruc,
        'usuario_sol': 'MODDATOS',
        'clave_sol': 'MODDATOS',
    },
)
print('SUNAT:', resultado)
