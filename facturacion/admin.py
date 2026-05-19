from django.contrib import admin
from .models import (
    TipoDocumento, TipoAfectacion, Unidad, Moneda, TipoComprobante,
    Emisor, Cliente, Serie, Producto, Comprobante, Detalle, Cuota,
    EnvioResumen, EnvioResumenDetalle
)

# Registro básico de tablas maestras de SUNAT
admin.site.register(TipoDocumento)
admin.site.register(TipoAfectacion)
admin.site.register(Unidad)
admin.site.register(Moneda)
admin.site.register(TipoComprobante)
admin.site.register(Serie)

# Configuraciones visuales personalizadas para catálogos principales
@admin.register(Emisor)
class EmisorAdmin(admin.ModelAdmin):
    list_display = ('ruc', 'razon_social', 'usuario_sol', 'porcetajeigv')
    search_fields = ('ruc', 'razon_social')

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ('nrodoc', 'razon_social', 'direccion')
    search_fields = ('nrodoc', 'razon_social')

@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('codigo_sunat', 'nombre', 'valor_unitario')
    search_fields = ('codigo_sunat', 'nombre')

# Registro de módulos transaccionales
admin.site.register(Comprobante)
admin.site.register(Detalle)
admin.site.register(Cuota)
admin.site.register(EnvioResumen)
admin.site.register(EnvioResumenDetalle)
