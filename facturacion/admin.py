from django.contrib import admin

from .models import (
    Cliente,
    Comprobante,
    DetalleComprobante,
    Empresa,
    LogEnvioSUNAT,
    Producto,
    SerieComprobante,
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("ruc", "razon_social", "nombre_comercial", "activo")
    search_fields = ("ruc", "razon_social", "nombre_comercial")
    list_filter = ("activo", "departamento", "provincia")
    readonly_fields = ("creado_en", "actualizado_en")


@admin.register(SerieComprobante)
class SerieComprobanteAdmin(admin.ModelAdmin):
    list_display = (
        "empresa",
        "tipo_comprobante",
        "serie",
        "correlativo_actual",
        "activo",
    )
    search_fields = ("empresa__ruc", "empresa__razon_social", "serie")
    list_filter = ("tipo_comprobante", "activo")
    readonly_fields = ("creado_en", "actualizado_en")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "tipo_documento",
        "numero_documento",
        "razon_social",
        "email",
        "activo",
    )
    search_fields = ("numero_documento", "razon_social", "email")
    list_filter = ("tipo_documento", "activo")
    readonly_fields = ("creado_en", "actualizado_en")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "descripcion",
        "unidad_medida",
        "precio_unitario",
        "afecto_igv",
        "activo",
    )
    search_fields = ("codigo", "descripcion", "codigo_sunat_unspsc")
    list_filter = ("unidad_medida", "afecto_igv", "activo")
    readonly_fields = ("creado_en", "actualizado_en")


class DetalleComprobanteInline(admin.TabularInline):
    model = DetalleComprobante
    extra = 0
    readonly_fields = ("subtotal", "igv_linea", "total_linea", "creado_en", "actualizado_en")
    fields = (
        "producto",
        "descripcion",
        "cantidad",
        "unidad_medida",
        "precio_unitario",
        "descuento",
        "subtotal",
        "igv_linea",
        "total_linea",
        "codigo_afectacion_igv",
    )


@admin.register(Comprobante)
class ComprobanteAdmin(admin.ModelAdmin):
    list_display = (
        "numero_formateado",
        "empresa",
        "cliente",
        "tipo_comprobante",
        "fecha_emision",
        "total",
        "estado",
    )
    search_fields = (
        "empresa__ruc",
        "cliente__numero_documento",
        "cliente__razon_social",
        "serie__serie",
        "numero",
    )
    list_filter = ("tipo_comprobante", "estado", "moneda", "fecha_emision")
    readonly_fields = ("creado_en", "actualizado_en")
    inlines = [DetalleComprobanteInline]


@admin.register(DetalleComprobante)
class DetalleComprobanteAdmin(admin.ModelAdmin):
    list_display = (
        "comprobante",
        "producto",
        "cantidad",
        "precio_unitario",
        "subtotal",
        "igv_linea",
        "total_linea",
    )
    search_fields = ("comprobante__serie__serie", "producto__codigo", "descripcion")
    list_filter = ("unidad_medida", "codigo_afectacion_igv")
    readonly_fields = ("creado_en", "actualizado_en")


@admin.register(LogEnvioSUNAT)
class LogEnvioSUNATAdmin(admin.ModelAdmin):
    list_display = (
        "comprobante",
        "fecha_envio",
        "estado_respuesta",
        "codigo_respuesta",
    )
    search_fields = ("comprobante__serie__serie", "codigo_respuesta", "descripcion")
    list_filter = ("estado_respuesta", "fecha_envio")
    readonly_fields = ("fecha_envio",)
