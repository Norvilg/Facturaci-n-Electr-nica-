# Generated manually for FASE 2 model rebuild.

import decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("facturacion", "0001_initial"),
    ]

    operations = [
        migrations.DeleteModel(name="EnvioResumenDetalle"),
        migrations.DeleteModel(name="Cuota"),
        migrations.DeleteModel(name="Detalle"),
        migrations.DeleteModel(name="Comprobante"),
        migrations.DeleteModel(name="Cliente"),
        migrations.DeleteModel(name="Producto"),
        migrations.DeleteModel(name="Serie"),
        migrations.DeleteModel(name="Emisor"),
        migrations.DeleteModel(name="EnvioResumen"),
        migrations.DeleteModel(name="Moneda"),
        migrations.DeleteModel(name="TipoAfectacion"),
        migrations.DeleteModel(name="TipoComprobante"),
        migrations.DeleteModel(name="TipoDocumento"),
        migrations.DeleteModel(name="Unidad"),
        migrations.CreateModel(
            name="Cliente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tipo_documento",
                    models.CharField(
                        choices=[
                            ("0", "Sin documento"),
                            ("1", "DNI"),
                            ("4", "Carnet extranjeria"),
                            ("6", "RUC"),
                            ("7", "Pasaporte"),
                        ],
                        max_length=1,
                    ),
                ),
                ("numero_documento", models.CharField(max_length=15)),
                ("razon_social", models.CharField(max_length=150)),
                ("direccion", models.CharField(blank=True, max_length=250)),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("activo", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "cliente",
                "ordering": ["razon_social"],
            },
        ),
        migrations.CreateModel(
            name="Empresa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "ruc",
                    models.CharField(
                        max_length=11,
                        unique=True,
                        validators=[
                            django.core.validators.RegexValidator(
                                "^\\d{11}$",
                                "El RUC debe tener 11 digitos.",
                            )
                        ],
                    ),
                ),
                ("razon_social", models.CharField(max_length=150)),
                ("nombre_comercial", models.CharField(blank=True, max_length=150)),
                ("direccion", models.CharField(max_length=250)),
                ("ubigeo", models.CharField(default="150101", max_length=6)),
                ("departamento", models.CharField(default="LIMA", max_length=100)),
                ("provincia", models.CharField(default="LIMA", max_length=100)),
                ("distrito", models.CharField(default="LIMA", max_length=100)),
                ("regimen_tributario", models.CharField(blank=True, max_length=100)),
                ("activo", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "empresa",
                "ordering": ["razon_social"],
            },
        ),
        migrations.CreateModel(
            name="Producto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(max_length=30, unique=True)),
                ("descripcion", models.CharField(max_length=250)),
                ("unidad_medida", models.CharField(default="NIU", max_length=3)),
                (
                    "precio_unitario",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))],
                    ),
                ),
                ("afecto_igv", models.BooleanField(default=True)),
                ("codigo_sunat_unspsc", models.CharField(default="10191509", max_length=8)),
                ("activo", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "producto",
                "ordering": ["descripcion"],
            },
        ),
        migrations.CreateModel(
            name="SerieComprobante",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "tipo_comprobante",
                    models.CharField(
                        choices=[
                            ("01", "Factura"),
                            ("03", "Boleta"),
                            ("07", "Nota de Credito"),
                            ("08", "Nota de Debito"),
                        ],
                        max_length=2,
                    ),
                ),
                ("serie", models.CharField(max_length=4)),
                ("correlativo_actual", models.PositiveIntegerField(default=1)),
                ("activo", models.BooleanField(default=True)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "empresa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="series",
                        to="facturacion.empresa",
                    ),
                ),
            ],
            options={
                "db_table": "serie_comprobante",
                "ordering": ["empresa", "tipo_comprobante", "serie"],
            },
        ),
        migrations.CreateModel(
            name="Comprobante",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.PositiveIntegerField()),
                ("fecha_emision", models.DateField()),
                ("hora_emision", models.TimeField()),
                (
                    "tipo_comprobante",
                    models.CharField(
                        choices=[
                            ("01", "Factura"),
                            ("03", "Boleta"),
                            ("07", "Nota de Credito"),
                            ("08", "Nota de Debito"),
                        ],
                        max_length=2,
                    ),
                ),
                ("moneda", models.CharField(default="PEN", max_length=3)),
                ("forma_pago", models.CharField(default="Contado", max_length=20)),
                ("subtotal", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("igv", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("total", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                (
                    "descuento_total",
                    models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12),
                ),
                (
                    "estado",
                    models.CharField(
                        choices=[
                            ("BORRADOR", "Borrador"),
                            ("GENERADO", "Generado"),
                            ("FIRMADO", "Firmado"),
                            ("ENVIADO", "Enviado"),
                            ("ACEPTADO", "Aceptado"),
                            ("RECHAZADO", "Rechazado"),
                            ("ERROR", "Error"),
                            ("ANULADO", "Anulado"),
                        ],
                        default="BORRADOR",
                        max_length=20,
                    ),
                ),
                ("xml_firmado", models.CharField(blank=True, max_length=255)),
                ("zip_enviado", models.CharField(blank=True, max_length=255)),
                ("sunat_cdr", models.CharField(blank=True, max_length=255)),
                ("sunat_ticket", models.CharField(blank=True, max_length=100)),
                ("sunat_codigo_respuesta", models.CharField(blank=True, max_length=20)),
                ("sunat_descripcion", models.TextField(blank=True)),
                ("motivo_nota", models.CharField(blank=True, max_length=250)),
                ("tipo_nota", models.CharField(blank=True, max_length=2)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "cliente",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comprobantes",
                        to="facturacion.cliente",
                    ),
                ),
                (
                    "comprobante_referencia",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="notas_relacionadas",
                        to="facturacion.comprobante",
                    ),
                ),
                (
                    "empresa",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comprobantes",
                        to="facturacion.empresa",
                    ),
                ),
                (
                    "serie",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="comprobantes",
                        to="facturacion.seriecomprobante",
                    ),
                ),
            ],
            options={
                "db_table": "comprobante",
                "ordering": ["-fecha_emision", "-numero"],
            },
        ),
        migrations.CreateModel(
            name="DetalleComprobante",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "descripcion",
                    models.CharField(blank=True, max_length=250),
                ),
                (
                    "cantidad",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.01"))],
                    ),
                ),
                ("unidad_medida", models.CharField(blank=True, default="NIU", max_length=3)),
                (
                    "precio_unitario",
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=12,
                        validators=[django.core.validators.MinValueValidator(decimal.Decimal("0.00"))],
                    ),
                ),
                ("descuento", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("subtotal", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("igv_linea", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("total_linea", models.DecimalField(decimal_places=2, default=decimal.Decimal("0.00"), max_digits=12)),
                ("codigo_afectacion_igv", models.CharField(default="10", max_length=2)),
                ("creado_en", models.DateTimeField(auto_now_add=True)),
                ("actualizado_en", models.DateTimeField(auto_now=True)),
                (
                    "comprobante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="detalles",
                        to="facturacion.comprobante",
                    ),
                ),
                (
                    "producto",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="detalles",
                        to="facturacion.producto",
                    ),
                ),
            ],
            options={
                "db_table": "detalle_comprobante",
                "ordering": ["id"],
            },
        ),
        migrations.CreateModel(
            name="LogEnvioSUNAT",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha_envio", models.DateTimeField(auto_now_add=True)),
                ("estado_respuesta", models.CharField(max_length=30)),
                ("codigo_respuesta", models.CharField(blank=True, max_length=20)),
                ("descripcion", models.TextField(blank=True)),
                ("request_xml_path", models.CharField(blank=True, max_length=255)),
                ("response_cdr_path", models.CharField(blank=True, max_length=255)),
                (
                    "comprobante",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs_sunat",
                        to="facturacion.comprobante",
                    ),
                ),
            ],
            options={
                "db_table": "log_envio_sunat",
                "ordering": ["-fecha_envio"],
            },
        ),
        migrations.AddConstraint(
            model_name="cliente",
            constraint=models.UniqueConstraint(
                fields=("tipo_documento", "numero_documento"),
                name="uq_cliente_tipo_numero_documento",
            ),
        ),
        migrations.AddConstraint(
            model_name="seriecomprobante",
            constraint=models.UniqueConstraint(
                fields=("empresa", "tipo_comprobante", "serie"),
                name="uq_serie_empresa_tipo_serie",
            ),
        ),
        migrations.AddConstraint(
            model_name="seriecomprobante",
            constraint=models.CheckConstraint(
                condition=models.Q(("correlativo_actual__gte", 1)),
                name="ck_serie_correlativo_actual_gte_1",
            ),
        ),
        migrations.AddConstraint(
            model_name="comprobante",
            constraint=models.UniqueConstraint(
                fields=("empresa", "tipo_comprobante", "serie", "numero"),
                name="uq_comprobante_empresa_tipo_serie_numero",
            ),
        ),
        migrations.AddConstraint(
            model_name="comprobante",
            constraint=models.CheckConstraint(condition=models.Q(("numero__gte", 1)), name="ck_comprobante_numero_gte_1"),
        ),
        migrations.AddConstraint(
            model_name="comprobante",
            constraint=models.CheckConstraint(
                condition=models.Q(("subtotal__gte", 0)),
                name="ck_comprobante_subtotal_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="comprobante",
            constraint=models.CheckConstraint(condition=models.Q(("igv__gte", 0)), name="ck_comprobante_igv_gte_0"),
        ),
        migrations.AddConstraint(
            model_name="comprobante",
            constraint=models.CheckConstraint(condition=models.Q(("total__gte", 0)), name="ck_comprobante_total_gte_0"),
        ),
        migrations.AddConstraint(
            model_name="detallecomprobante",
            constraint=models.CheckConstraint(condition=models.Q(("cantidad__gt", 0)), name="ck_detalle_cantidad_gt_0"),
        ),
        migrations.AddConstraint(
            model_name="detallecomprobante",
            constraint=models.CheckConstraint(
                condition=models.Q(("precio_unitario__gte", 0)),
                name="ck_detalle_precio_unitario_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="detallecomprobante",
            constraint=models.CheckConstraint(
                condition=models.Q(("descuento__gte", 0)),
                name="ck_detalle_descuento_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="detallecomprobante",
            constraint=models.CheckConstraint(condition=models.Q(("subtotal__gte", 0)), name="ck_detalle_subtotal_gte_0"),
        ),
        migrations.AddConstraint(
            model_name="detallecomprobante",
            constraint=models.CheckConstraint(
                condition=models.Q(("igv_linea__gte", 0)),
                name="ck_detalle_igv_linea_gte_0",
            ),
        ),
        migrations.AddConstraint(
            model_name="detallecomprobante",
            constraint=models.CheckConstraint(
                condition=models.Q(("total_linea__gte", 0)),
                name="ck_detalle_total_linea_gte_0",
            ),
        ),
    ]
