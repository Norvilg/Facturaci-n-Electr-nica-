from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from facturacion.constants import (
    AFECTACION_GRAVADO,
    ESTADO_BORRADOR,
    MONEDA_PEN,
    TIPO_BOLETA,
    TIPO_DOC_DNI,
    TIPO_DOC_RUC,
    TIPO_DOC_SIN_DOCUMENTO,
    TIPO_FACTURA,
    TIPO_NOTA_CREDITO,
    TIPO_NOTA_DEBITO,
    UNIDAD_NIU,
)
from facturacion.models import (
    Cliente,
    Comprobante,
    DetalleComprobante,
    Empresa,
    Producto,
    SerieComprobante,
)


DEMO_RUC = "20100066603"


class Command(BaseCommand):
    help = "Carga datos demo mínimos para facturacion electronica SUNAT."

    def handle(self, *args, **options):
        self.stdout.write("Creando datos demo de facturacion electronica...")

        try:
            with transaction.atomic():
                empresa = self._crear_empresa()
                series = self._crear_series(empresa)
                clientes = self._crear_clientes()
                productos = self._crear_productos()
                self._crear_comprobantes_demo(empresa, series, clientes, productos)
        except Exception as exc:
            raise CommandError(f"No se pudieron cargar los datos demo: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("Datos demo cargados correctamente."))

    def _crear_empresa(self):
        empresa, _created = Empresa.objects.update_or_create(
            ruc=DEMO_RUC,
            defaults={
                "razon_social": "MI EMPRESA DEMO SAC",
                "nombre_comercial": "MI EMPRESA DEMO",
                "direccion": "AV. PRINCIPAL 123 - LIMA",
                "ubigeo": "150101",
                "departamento": "LIMA",
                "provincia": "LIMA",
                "distrito": "LIMA",
                "regimen_tributario": "GENERAL",
                "activo": True,
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Empresa demo creada/actualizada: {empresa.ruc}"))
        return empresa

    def _crear_series(self, empresa):
        specs = (
            (TIPO_FACTURA, "F001"),
            (TIPO_BOLETA, "B001"),
            # El modelo admite series no vacías para notas. Se usan FC01/FD01 para
            # distinguirlas de factura/boleta sin forzar aún la serie del documento afectado.
            (TIPO_NOTA_CREDITO, "FC01"),
            (TIPO_NOTA_DEBITO, "FD01"),
        )
        series = {}
        for tipo, serie_texto in specs:
            serie, _created = SerieComprobante.objects.update_or_create(
                empresa=empresa,
                tipo_comprobante=tipo,
                serie=serie_texto,
                defaults={
                    "correlativo_actual": 1,
                    "activo": True,
                },
            )
            series[tipo] = serie
            self.stdout.write(self.style.SUCCESS(f"Serie {serie_texto} creada/actualizada"))
        return series

    def _crear_clientes(self):
        specs = (
            (
                "ruc",
                TIPO_DOC_RUC,
                "20123456789",
                {
                    "razon_social": "CLIENTE DEMO SAC",
                    "direccion": "CALLE LOS CLIENTES 456 - LIMA",
                    "email": "cliente.ruc.demo@example.com",
                    "activo": True,
                },
            ),
            (
                "dni",
                TIPO_DOC_DNI,
                "12345678",
                {
                    "razon_social": "JUAN PEREZ DEMO",
                    "direccion": "AV. CLIENTE 123 - LIMA",
                    "email": "cliente.dni.demo@example.com",
                    "activo": True,
                },
            ),
            (
                "varios",
                TIPO_DOC_SIN_DOCUMENTO,
                "00000000",
                {
                    "razon_social": "CLIENTE VARIOS",
                    "direccion": "LIMA",
                    "email": "",
                    "activo": True,
                },
            ),
        )
        clientes = {}
        for key, tipo_documento, numero_documento, defaults in specs:
            cliente, _created = Cliente.objects.update_or_create(
                tipo_documento=tipo_documento,
                numero_documento=numero_documento,
                defaults=defaults,
            )
            clientes[key] = cliente

        self.stdout.write(self.style.SUCCESS("Cliente RUC creado/actualizado"))
        self.stdout.write(self.style.SUCCESS("Cliente DNI creado/actualizado"))
        self.stdout.write(self.style.SUCCESS("Cliente varios creado/actualizado"))
        return clientes

    def _crear_productos(self):
        specs = (
            (
                "PROD001",
                {
                    "descripcion": "MONITOR LED 24 PULGADAS",
                    "unidad_medida": UNIDAD_NIU,
                    "precio_unitario": Decimal("200.00"),
                    "afecto_igv": True,
                    "codigo_sunat_unspsc": "43211902",
                    "activo": True,
                },
            ),
            (
                "PROD002",
                {
                    "descripcion": "TECLADO MECANICO",
                    "unidad_medida": UNIDAD_NIU,
                    "precio_unitario": Decimal("80.00"),
                    "afecto_igv": True,
                    "codigo_sunat_unspsc": "43211706",
                    "activo": True,
                },
            ),
            (
                "PROD003",
                {
                    "descripcion": "SERVICIO DE SOPORTE TECNICO",
                    "unidad_medida": "ZZ",
                    "precio_unitario": Decimal("150.00"),
                    "afecto_igv": True,
                    "codigo_sunat_unspsc": "81111811",
                    "activo": True,
                },
            ),
        )
        productos = {}
        for codigo, defaults in specs:
            producto, _created = Producto.objects.update_or_create(
                codigo=codigo,
                defaults=defaults,
            )
            productos[codigo] = producto

        self.stdout.write(self.style.SUCCESS("Productos demo creados/actualizados"))
        return productos

    def _crear_comprobantes_demo(self, empresa, series, clientes, productos):
        factura = self._crear_comprobante_borrador(
            empresa=empresa,
            serie=series[TIPO_FACTURA],
            numero=1,
            tipo_comprobante=TIPO_FACTURA,
            cliente=clientes["ruc"],
            producto=productos["PROD001"],
            cantidad=Decimal("2.00"),
            precio_unitario=Decimal("200.00"),
        )
        self.stdout.write(
            self.style.SUCCESS(f"Factura demo BORRADOR creada/actualizada: {factura.numero_formateado()}")
        )

        boleta = self._crear_comprobante_borrador(
            empresa=empresa,
            serie=series[TIPO_BOLETA],
            numero=1,
            tipo_comprobante=TIPO_BOLETA,
            cliente=clientes["dni"],
            producto=productos["PROD002"],
            cantidad=Decimal("1.00"),
            precio_unitario=Decimal("80.00"),
        )
        self.stdout.write(
            self.style.SUCCESS(f"Boleta demo BORRADOR creada/actualizada: {boleta.numero_formateado()}")
        )

    def _crear_comprobante_borrador(
        self,
        *,
        empresa,
        serie,
        numero,
        tipo_comprobante,
        cliente,
        producto,
        cantidad,
        precio_unitario,
    ):
        now = timezone.localtime()
        comprobante, _created = Comprobante.objects.update_or_create(
            empresa=empresa,
            serie=serie,
            numero=numero,
            tipo_comprobante=tipo_comprobante,
            defaults={
                "fecha_emision": now.date(),
                "hora_emision": now.time().replace(microsecond=0),
                "cliente": cliente,
                "moneda": MONEDA_PEN,
                "forma_pago": "Contado",
                "estado": ESTADO_BORRADOR,
            },
        )
        DetalleComprobante.objects.update_or_create(
            comprobante=comprobante,
            producto=producto,
            defaults={
                "descripcion": producto.descripcion,
                "cantidad": cantidad,
                "unidad_medida": producto.unidad_medida,
                "precio_unitario": precio_unitario,
                "descuento": Decimal("0.00"),
                "codigo_afectacion_igv": AFECTACION_GRAVADO,
            },
        )
        comprobante.recalcular_totales()
        return comprobante
