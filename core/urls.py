from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
<<<<<<< HEAD
from django.urls import path, include
=======
from django.contrib.auth.views import LogoutView
from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from facturacion.api_docs import (
    doc_api_facturas, doc_api_boletas, doc_buscar_comprobante,
    doc_api_notas_credito, doc_api_notas_debito,
)
from facturacion.views_auth import FacturacionLoginView
from facturacion.views import (
    dashboard, perfil_emisor_view,
    lista_comprobantes_view, imprimir_comprobante,
    api_facturas, api_boletas, api_notas_credito, api_notas_debito, api_guias_remision,
    buscar_comprobante,
)
from facturacion.views_mantenimiento import (
    lista_clientes_view, cliente_crear_view, cliente_editar_view,
    cliente_eliminar_view, cliente_detalle_view,
    lista_productos_view, producto_crear_view, producto_editar_view, producto_eliminar_view,
    libro_ventas_view, libro_ventas_exportar_view,
)
>>>>>>> edin

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),
<<<<<<< HEAD
=======
    path('login/', FacturacionLoginView.as_view(), name='login'),
    path('cerrar-sesion/', LogoutView.as_view(), name='logout'),
    path('', dashboard, name='dashboard'),  # <-- Ruta raíz principal
    path('clientes/', lista_clientes_view, name='lista_clientes'),
    path('clientes/nuevo/', cliente_crear_view, name='cliente_crear'),
    path('clientes/<int:pk>/', cliente_detalle_view, name='cliente_detalle'),
    path('clientes/<int:pk>/editar/', cliente_editar_view, name='cliente_editar'),
    path('clientes/<int:pk>/eliminar/', cliente_eliminar_view, name='cliente_eliminar'),
    path('productos/', lista_productos_view, name='lista_productos'),
    path('productos/nuevo/', producto_crear_view, name='producto_crear'),
    path('productos/<int:pk>/editar/', producto_editar_view, name='producto_editar'),
    path('productos/<int:pk>/eliminar/', producto_eliminar_view, name='producto_eliminar'),
    path('reportes/libro-ventas/', libro_ventas_view, name='libro_ventas'),
    path('reportes/libro-ventas/exportar/', libro_ventas_exportar_view, name='libro_ventas_exportar'),
    path('perfil/', perfil_emisor_view, name='perfil_emisor'),
>>>>>>> edin

    # Auth JWT + login
    path('', include('api.urls')),

<<<<<<< HEAD
    # Facturación (dashboard, comprobantes, clientes, productos, etc.)
    path('', include('facturacion.urls')),
=======
    # LISTO: Esta es la nueva ruta que activa la Nota de Crédito
    path('api/notas-credito/', api_notas_credito, name='api_notas_credito'),
    # LISTO: Esta es la nueva ruta que activa la Nota de Débito
    path('api/notas-debito/', api_notas_debito, name='api_notas_debito'),
    # LISTO: Esta es la nueva ruta que activa la Guía de Remisión
    path('api/guias-remision/', api_guias_remision, name='api_guias_remision'),
    path('api/comprobantes/buscar/', buscar_comprobante, name='buscar_comprobante'),
    path('comprobantes/', lista_comprobantes_view, name='lista_comprobantes'),
    path('comprobantes/<int:pk>/imprimir/', imprimir_comprobante, name='imprimir_comprobante'),

    # Swagger / OpenAPI (rúbrica docente)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/facturas/', doc_api_facturas, name='doc_api_facturas'),
    path('api/docs/boletas/', doc_api_boletas, name='doc_api_boletas'),
    path('api/docs/notas-credito/', doc_api_notas_credito, name='doc_api_notas_credito'),
    path('api/docs/notas-debito/', doc_api_notas_debito, name='doc_api_notas_debito'),
    path('api/docs/comprobantes/buscar/', doc_buscar_comprobante, name='doc_buscar_comprobante'),
>>>>>>> edin
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.BASE_DIR / 'static',
    )
