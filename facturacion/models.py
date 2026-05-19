from django.db import models

class TipoDocumento(models.Model):
    id_tipo_doc = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=50)

    class Meta:
        db_table = 'tipo_documento'

class TipoAfectacion(models.Model):
    id_tipo_afectacion = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=50)
    letra = models.CharField(max_length=1)
    codigo = models.CharField(max_length=4)
    name = models.CharField(max_length=3)
    tipo = models.CharField(max_length=3, null=True, blank=True)

    class Meta:
        db_table = 'tipo_afectacion'

class Unidad(models.Model):
    id_version = models.AutoField(primary_key=True)  # Equivalente a id_unidad
    descripcion = models.CharField(max_length=60)

    class Meta:
        db_table = 'unidad'

class Moneda(models.Model):
    id_moneda = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=50)

    class Meta:
        db_table = 'moneda'

class TipoComprobante(models.Model):
    id_tipo_comprobante = models.AutoField(primary_key=True)
    descripcion = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'tipo_comprobante'

class Emisor(models.Model):
    id_emisor = models.AutoField(primary_key=True)
    tipodoc = models.CharField(max_length=1)
    ruc = models.CharField(max_length=11)
    razon_social = models.CharField(max_length=100)
    nombre_comercial = models.CharField(max_length=100)
    direccion = models.CharField(max_length=100, null=True, blank=True)
    pais = models.CharField(max_length=100, null=True, blank=True)
    departamento = models.CharField(max_length=100, null=True, blank=True)
    provincia = models.CharField(max_length=100, null=True, blank=True)
    distrito = models.CharField(max_length=100, null=True, blank=True)
    ubigeo = models.CharField(max_length=6, null=True, blank=True)
    usuario_sol = models.CharField(max_length=20)
    clave_sol = models.CharField(max_length=20)
    porcetajeigv = models.DecimalField(max_digits=15, decimal_places=6)

    class Meta:
        db_table = 'emisor'

class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nrodoc = models.CharField(max_length=15)
    razon_social = models.CharField(max_length=100)
    direccion = models.CharField(max_length=100)
    id_tipo_doc = models.ForeignKey(TipoDocumento, on_delete=models.PROTECT, db_column='id_tipo_doc')

    class Meta:
        db_table = 'cliente'

class Serie(models.Model):
    id_serie = models.AutoField(primary_key=True)
    serie = models.CharField(max_length=4)
    correlativo = models.IntegerField()
    id_tipo_comprobante = models.ForeignKey(TipoComprobante, on_delete=models.PROTECT, db_column='id_tipo_comprobante')

    class Meta:
        db_table = 'serie'

class Producto(models.Model):
    id_producto = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=255)
    valor_unitario = models.DecimalField(max_digits=15, decimal_places=2)
    codigo_sunat = models.CharField(max_length=12)
    id_unidad = models.ForeignKey(Unidad, on_delete=models.PROTECT, db_column='id_unidad')
    id_tipo_afectacion = models.ForeignKey(TipoAfectacion, on_delete=models.PROTECT, db_column='id_tipo_afectacion')

    class Meta:
        db_table = 'producto'

class Comprobante(models.Model):
    id_comprobante = models.AutoField(primary_key=True)
    id_emisor = models.ForeignKey(Emisor, on_delete=models.PROTECT, db_column='id_emisor')
    id_tipo_comprobante = models.ForeignKey(TipoComprobante, on_delete=models.PROTECT, db_column='id_tipo_comprobante')
    id_serie = models.ForeignKey(Serie, on_delete=models.PROTECT, db_column='id_serie')
    serie = models.CharField(max_length=4)
    correlativo = models.IntegerField()
    forma_pago = models.CharField(max_length=50)
    fecha_emision = models.DateField()
    fecha_vencimiento = models.DateField()
    id_moneda = models.ForeignKey(Moneda, on_delete=models.PROTECT, db_column='id_moneda')
    op_grabadas = models.DecimalField(max_digits=11, decimal_places=2)
    op_exoneradas = models.DecimalField(max_digits=11, decimal_places=2)
    op_inefactas = models.DecimalField(max_digits=11, decimal_places=2)
    igv = models.DecimalField(max_digits=11, decimal_places=2)
    total = models.DecimalField(max_digits=11, decimal_places=2)
    id_cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, db_column='id_cliente')
    tipo_comprobante_ref_id = models.CharField(max_length=4, null=True, blank=True)
    serie_ref = models.CharField(max_length=4, null=True, blank=True)
    correlativo_ref = models.IntegerField(null=True, blank=True)
    codmotivo = models.CharField(max_length=5, null=True, blank=True)
    nombrexml = models.CharField(max_length=50, null=True, blank=True)
    xmlbase64 = models.TextField(null=True, blank=True)  # mediumtext mapea a TextField en Postgres
    hash = models.TextField(null=True, blank=True)
    cdrbase64 = models.TextField(null=True, blank=True)
    codigo_sunat = models.CharField(max_length=20, null=True, blank=True)
    mensaje_sunat = models.CharField(max_length=100, null=True, blank=True)
    estado_comprobante = models.CharField(max_length=1, null=True, blank=True)

    class Meta:
        db_table = 'comprobante'

class Detalle(models.Model):
    id_detalle = models.AutoField(primary_key=True)
    id_comprobante = models.ForeignKey(Comprobante, on_delete=models.CASCADE, db_column='id_comprobante')
    item = models.IntegerField()
    id_producto = models.ForeignKey(Producto, on_delete=models.PROTECT, db_column='id_producto')
    cantidad = models.DecimalField(max_digits=15, decimal_places=6)
    valor_unitario = models.DecimalField(max_digits=15, decimal_places=6)
    precio_unitario = models.DecimalField(max_digits=15, decimal_places=6)
    igv = models.DecimalField(max_digits=15, decimal_places=6)
    porcentaje_igv = models.DecimalField(max_digits=15, decimal_places=6)
    valor_total = models.DecimalField(max_digits=15, decimal_places=6)
    importe_total = models.DecimalField(max_digits=15, decimal_places=6)

    class Meta:
        db_table = 'detalle'

class Cuota(models.Model):
    id_cuota = models.AutoField(primary_key=True)
    id_comprobante = models.ForeignKey(Comprobante, on_delete=models.CASCADE, db_column='id_comprobante')
    numero = models.CharField(max_length=3, null=True, blank=True)
    importe = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=1, null=True, blank=True)

    class Meta:
        db_table = 'cuota'

class EnvioResumen(models.Model):
    id_envio_resumen = models.AutoField(primary_key=True)
    fecha_envio = models.DateField()
    fecha_referencia = models.DateField()
    correlativo = models.IntegerField()
    resumen = models.SmallIntegerField()
    baja = models.SmallIntegerField()
    nombrexml = models.CharField(max_length=50)
    mensaje_sunat = models.CharField(max_length=20)
    codigo_sunat = models.CharField(max_length=20)
    ticket = models.CharField(max_length=50)
    estado = models.CharField(max_length=1)

    class Meta:
        db_table = 'envio_resumen'

class EnvioResumenDetalle(models.Model):
    id_resumen_detalle = models.AutoField(primary_key=True)
    id_comprobante = models.ForeignKey(Comprobante, on_delete=models.CASCADE, db_column='id_comprobante')
    id_envio_resumen = models.ForeignKey(EnvioResumen, on_delete=models.CASCADE, db_column='id_envio_resumen')
    condicion = models.SmallIntegerField()

    class Meta:
        db_table = 'envio_resumen_detalle'
