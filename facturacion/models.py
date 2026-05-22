from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from .constants import (
    AFECTACION_GRAVADO,
    ESTADO_BORRADOR,
    ESTADOS_COMPROBANTE,
    IGV_RATE,
    MONEDA_PEN,
    SUNAT_DEMO_RUC,
    TIPO_BOLETA,
    TIPO_DOC_DNI,
    TIPO_DOC_RUC,
    TIPO_FACTURA,
    TIPO_NOTA_CREDITO,
    TIPO_NOTA_DEBITO,
    TIPOS_COMPROBANTE,
    TIPOS_DOCUMENTO_IDENTIDAD,
    UNIDAD_NIU,
)


TWOPLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return Decimal(value or "0").quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def only_digits(value: str) -> bool:
    return bool(value) and value.isdigit()


class _DescripcionCompat:
    def __init__(self, descripcion: str):
        self.descripcion = descripcion


class Empresa(models.Model):
    ruc = models.CharField(
        max_length=11,
        unique=True,
        validators=[RegexValidator(r"^\d{11}$", "El RUC debe tener 11 digitos.")],
    )
    razon_social = models.CharField(max_length=150)
    nombre_comercial = models.CharField(max_length=150, blank=True)
    direccion = models.CharField(max_length=250)
    ubigeo = models.CharField(max_length=6, default="150101")
    departamento = models.CharField(max_length=100, default="LIMA")
    provincia = models.CharField(max_length=100, default="LIMA")
    distrito = models.CharField(max_length=100, default="LIMA")
    regimen_tributario = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "empresa"
        ordering = ["razon_social"]

    def clean(self):
        if not only_digits(self.ruc) or len(self.ruc) != 11:
            raise ValidationError({"ruc": "El RUC debe tener 11 digitos."})

    def __str__(self):
        return f"{self.ruc} - {self.razon_social}"


class SerieComprobante(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="series")
    tipo_comprobante = models.CharField(max_length=2, choices=TIPOS_COMPROBANTE)
    serie = models.CharField(max_length=4)
    correlativo_actual = models.PositiveIntegerField(default=1)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "serie_comprobante"
        ordering = ["empresa", "tipo_comprobante", "serie"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "tipo_comprobante", "serie"],
                name="uq_serie_empresa_tipo_serie",
            ),
            models.CheckConstraint(
                condition=models.Q(correlativo_actual__gte=1),
                name="ck_serie_correlativo_actual_gte_1",
            ),
        ]

    def clean(self):
        serie = (self.serie or "").upper()
        if self.tipo_comprobante == TIPO_FACTURA and not serie.startswith("F"):
            raise ValidationError({"serie": "La serie de factura debe iniciar con F."})
        if self.tipo_comprobante == TIPO_BOLETA and not serie.startswith("B"):
            raise ValidationError({"serie": "La serie de boleta debe iniciar con B."})
        if self.tipo_comprobante in {TIPO_NOTA_CREDITO, TIPO_NOTA_DEBITO} and not serie:
            raise ValidationError({"serie": "La serie de la nota es obligatoria."})
        if self.correlativo_actual < 1:
            raise ValidationError(
                {"correlativo_actual": "El correlativo debe ser mayor o igual a 1."}
            )
        self.serie = serie

    def siguiente_numero(self) -> int:
        return self.correlativo_actual

    def incrementar_correlativo(self):
        self.correlativo_actual += 1
        self.save(update_fields=["correlativo_actual", "actualizado_en"])

    def serie_numero_formateado(self, numero: int) -> str:
        return f"{self.serie}-{numero:08d}"

    @property
    def correlativo(self):
        return self.correlativo_actual

    def __str__(self):
        return f"{self.serie} ({self.get_tipo_comprobante_display()})"


class Cliente(models.Model):
    tipo_documento = models.CharField(max_length=1, choices=TIPOS_DOCUMENTO_IDENTIDAD)
    numero_documento = models.CharField(max_length=15)
    razon_social = models.CharField(max_length=150)
    direccion = models.CharField(max_length=250, blank=True)
    email = models.EmailField(blank=True)
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "cliente"
        ordering = ["razon_social"]
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_documento", "numero_documento"],
                name="uq_cliente_tipo_numero_documento",
            )
        ]

    def clean(self):
        if self.activo and not (self.razon_social or "").strip():
            raise ValidationError({"razon_social": "El cliente activo requiere nombre."})
        if self.tipo_documento == TIPO_DOC_DNI:
            if not only_digits(self.numero_documento) or len(self.numero_documento) != 8:
                raise ValidationError({"numero_documento": "El DNI debe tener 8 digitos."})
        if self.tipo_documento == TIPO_DOC_RUC:
            if not only_digits(self.numero_documento) or len(self.numero_documento) != 11:
                raise ValidationError({"numero_documento": "El RUC debe tener 11 digitos."})

    @property
    def nrodoc(self):
        return self.numero_documento

    @property
    def id_tipo_doc(self):
        return _DescripcionCompat(self.get_tipo_documento_display())

    def __str__(self):
        return f"{self.numero_documento} - {self.razon_social}"


class Producto(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    descripcion = models.CharField(max_length=250)
    unidad_medida = models.CharField(max_length=3, default=UNIDAD_NIU)
    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    afecto_igv = models.BooleanField(default=True)
    codigo_sunat_unspsc = models.CharField(max_length=8, default="10191509")
    activo = models.BooleanField(default=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "producto"
        ordering = ["descripcion"]

    def clean(self):
        if not (self.descripcion or "").strip():
            raise ValidationError({"descripcion": "La descripcion es obligatoria."})
        if not (self.unidad_medida or "").strip():
            raise ValidationError({"unidad_medida": "La unidad de medida es obligatoria."})
        if self.precio_unitario < 0:
            raise ValidationError({"precio_unitario": "El precio no puede ser negativo."})
        self.unidad_medida = self.unidad_medida.upper()

    @property
    def nombre(self):
        return self.descripcion

    @property
    def valor_unitario(self):
        return self.precio_unitario

    @property
    def codigo_sunat(self):
        return self.codigo_sunat_unspsc

    @property
    def id_unidad(self):
        return _DescripcionCompat(self.unidad_medida)

    @property
    def id_tipo_afectacion(self):
        return _DescripcionCompat("Gravado" if self.afecto_igv else "Inafecto")

    def __str__(self):
        return f"{self.codigo} - {self.descripcion}"


class Comprobante(models.Model):
    empresa = models.ForeignKey(Empresa, on_delete=models.PROTECT, related_name="comprobantes")
    serie = models.ForeignKey(
        SerieComprobante,
        on_delete=models.PROTECT,
        related_name="comprobantes",
    )
    numero = models.PositiveIntegerField()
    fecha_emision = models.DateField()
    hora_emision = models.TimeField()
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="comprobantes")
    tipo_comprobante = models.CharField(max_length=2, choices=TIPOS_COMPROBANTE)
    moneda = models.CharField(max_length=3, default=MONEDA_PEN)
    forma_pago = models.CharField(max_length=20, default="Contado")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    igv = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    descuento_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    estado = models.CharField(max_length=20, choices=ESTADOS_COMPROBANTE, default=ESTADO_BORRADOR)
    xml_firmado = models.CharField(max_length=255, blank=True)
    zip_enviado = models.CharField(max_length=255, blank=True)
    sunat_cdr = models.CharField(max_length=255, blank=True)
    sunat_ticket = models.CharField(max_length=100, blank=True)
    sunat_codigo_respuesta = models.CharField(max_length=20, blank=True)
    sunat_descripcion = models.TextField(blank=True)
    comprobante_referencia = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="notas_relacionadas",
    )
    motivo_nota = models.CharField(max_length=250, blank=True)
    tipo_nota = models.CharField(max_length=2, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comprobante"
        ordering = ["-fecha_emision", "-numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "tipo_comprobante", "serie", "numero"],
                name="uq_comprobante_empresa_tipo_serie_numero",
            ),
            models.CheckConstraint(condition=models.Q(numero__gte=1), name="ck_comprobante_numero_gte_1"),
            models.CheckConstraint(condition=models.Q(subtotal__gte=0), name="ck_comprobante_subtotal_gte_0"),
            models.CheckConstraint(condition=models.Q(igv__gte=0), name="ck_comprobante_igv_gte_0"),
            models.CheckConstraint(condition=models.Q(total__gte=0), name="ck_comprobante_total_gte_0"),
        ]

    def clean(self):
        if self.numero < 1:
            raise ValidationError({"numero": "El numero debe ser mayor o igual a 1."})
        if self.serie_id and self.tipo_comprobante != self.serie.tipo_comprobante:
            raise ValidationError(
                {"tipo_comprobante": "El tipo debe coincidir con la serie."}
            )
        serie_texto = self.serie.serie if self.serie_id else ""
        if self.tipo_comprobante == TIPO_FACTURA and not serie_texto.startswith("F"):
            raise ValidationError({"serie": "La factura debe usar serie F."})
        if self.tipo_comprobante == TIPO_BOLETA and not serie_texto.startswith("B"):
            raise ValidationError({"serie": "La boleta debe usar serie B."})
        if self.tipo_comprobante == TIPO_FACTURA and self.cliente_id:
            if self.cliente.tipo_documento != TIPO_DOC_RUC:
                raise ValidationError({"cliente": "La factura debe emitirse a cliente RUC."})
        if self.tipo_comprobante in {TIPO_NOTA_CREDITO, TIPO_NOTA_DEBITO}:
            if not self.comprobante_referencia_id:
                raise ValidationError(
                    {"comprobante_referencia": "La nota requiere comprobante de referencia."}
                )
        for field in ("subtotal", "igv", "total", "descuento_total"):
            if getattr(self, field) < 0:
                raise ValidationError({field: "El importe no puede ser negativo."})

    def numero_formateado(self) -> str:
        return self.serie.serie_numero_formateado(self.numero)

    def nombre_archivo_sunat(self) -> str:
        # En envio real este RUC debe coincidir con SUNAT_CERT_RUC y el certificado.
        return f"{self.empresa.ruc}-{self.tipo_comprobante}-{self.serie.serie}-{self.numero:08d}"

    def recalcular_totales(self, guardar: bool = True):
        detalles = self.detalles.all()
        self.subtotal = money(sum((d.subtotal for d in detalles), Decimal("0.00")))
        self.igv = money(sum((d.igv_linea for d in detalles), Decimal("0.00")))
        self.descuento_total = money(sum((d.descuento for d in detalles), Decimal("0.00")))
        self.total = money(sum((d.total_linea for d in detalles), Decimal("0.00")))
        if guardar:
            self.save(update_fields=["subtotal", "igv", "descuento_total", "total", "actualizado_en"])

    def es_factura(self) -> bool:
        return self.tipo_comprobante == TIPO_FACTURA

    def es_boleta(self) -> bool:
        return self.tipo_comprobante == TIPO_BOLETA

    def es_nota_credito(self) -> bool:
        return self.tipo_comprobante == TIPO_NOTA_CREDITO

    def es_nota_debito(self) -> bool:
        return self.tipo_comprobante == TIPO_NOTA_DEBITO

    @property
    def correlativo(self):
        return self.numero

    @property
    def id_cliente(self):
        return self.cliente

    @property
    def id_emisor(self):
        return self.empresa

    @property
    def id_serie(self):
        return self.serie

    def __str__(self):
        return self.numero_formateado()


class DetalleComprobante(models.Model):
    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.CASCADE,
        related_name="detalles",
    )
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name="detalles")
    descripcion = models.CharField(max_length=250, blank=True)
    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    unidad_medida = models.CharField(max_length=3, default=UNIDAD_NIU, blank=True)
    precio_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    descuento = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    igv_linea = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    total_linea = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    codigo_afectacion_igv = models.CharField(max_length=2, default=AFECTACION_GRAVADO)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "detalle_comprobante"
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(cantidad__gt=0), name="ck_detalle_cantidad_gt_0"),
            models.CheckConstraint(
                condition=models.Q(precio_unitario__gte=0),
                name="ck_detalle_precio_unitario_gte_0",
            ),
            models.CheckConstraint(condition=models.Q(descuento__gte=0), name="ck_detalle_descuento_gte_0"),
            models.CheckConstraint(condition=models.Q(subtotal__gte=0), name="ck_detalle_subtotal_gte_0"),
            models.CheckConstraint(condition=models.Q(igv_linea__gte=0), name="ck_detalle_igv_linea_gte_0"),
            models.CheckConstraint(condition=models.Q(total_linea__gte=0), name="ck_detalle_total_linea_gte_0"),
        ]

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError({"cantidad": "La cantidad debe ser mayor que cero."})
        if self.precio_unitario < 0:
            raise ValidationError({"precio_unitario": "El precio no puede ser negativo."})
        if self.descuento < 0:
            raise ValidationError({"descuento": "El descuento no puede ser negativo."})

    def calcular_totales(self):
        base = money((self.cantidad * self.precio_unitario) - self.descuento)
        if base < 0:
            raise ValidationError({"descuento": "El descuento no puede superar el subtotal."})
        self.subtotal = base
        self.igv_linea = money(base * IGV_RATE) if self.producto.afecto_igv else Decimal("0.00")
        self.total_linea = money(self.subtotal + self.igv_linea)

    def save(self, *args, **kwargs):
        if self.producto_id:
            if not self.descripcion:
                self.descripcion = self.producto.descripcion
            if not self.unidad_medida:
                self.unidad_medida = self.producto.unidad_medida
            self.calcular_totales()
        super().save(*args, **kwargs)

    @property
    def id_comprobante(self):
        return self.comprobante

    @property
    def id_producto(self):
        return self.producto

    @property
    def valor_unitario(self):
        return self.precio_unitario

    @property
    def igv(self):
        return self.igv_linea

    @property
    def valor_total(self):
        return self.subtotal

    @property
    def importe_total(self):
        return self.total_linea

    def __str__(self):
        return f"{self.comprobante} - {self.descripcion}"


class LogEnvioSUNAT(models.Model):
    comprobante = models.ForeignKey(
        Comprobante,
        on_delete=models.CASCADE,
        related_name="logs_sunat",
    )
    fecha_envio = models.DateTimeField(auto_now_add=True)
    estado_respuesta = models.CharField(max_length=30)
    codigo_respuesta = models.CharField(max_length=20, blank=True)
    descripcion = models.TextField(blank=True)
    request_xml_path = models.CharField(max_length=255, blank=True)
    response_cdr_path = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "log_envio_sunat"
        ordering = ["-fecha_envio"]

    def __str__(self):
        return f"{self.comprobante} - {self.estado_respuesta} - {self.codigo_respuesta}"


# Compatibility aliases for legacy imports. Their runtime behavior will be
# replaced by the canonical models in the next application phases.
Emisor = Empresa
Serie = SerieComprobante
Detalle = DetalleComprobante


class TipoDocumento:
    pass


class TipoAfectacion:
    pass


class Unidad:
    pass


class Moneda:
    pass


class TipoComprobante:
    pass


class Cuota:
    pass


class EnvioResumen:
    pass


class EnvioResumenDetalle:
    pass
