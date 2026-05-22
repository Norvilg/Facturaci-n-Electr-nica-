from django.urls import path
from .views import (
    dashboard,
    lista_clientes_view,
    lista_productos_view,
    perfil_emisor_view,
    lista_comprobantes_view,
    imprimir_comprobante,
    api_facturas,
    api_boletas,
    api_notas_credito,
    api_notas_debito,
    api_guias_remision,
    buscar_comprobante,
    logout_view,
)

urlpatterns = [
    # Vistas principales
    path('',                                dashboard,              name='dashboard'),
    path('clientes/',                        lista_clientes_view,    name='lista_clientes'),
    path('productos/',                       lista_productos_view,   name='lista_productos'),
    path('perfil/',                          perfil_emisor_view,     name='perfil_emisor'),
    path('comprobantes/',                    lista_comprobantes_view,name='lista_comprobantes'),
    path('comprobantes/<int:pk>/imprimir/',  imprimir_comprobante,   name='imprimir_comprobante'),
    path('cerrar-sesion/',                   logout_view,            name='logout'),

    # API endpoints de facturación
    path('api/facturas/',                    api_facturas,           name='api_facturas'),
    path('api/boletas/',                     api_boletas,            name='api_boletas'),
    path('api/notas-credito/',               api_notas_credito,      name='api_notas_credito'),
    path('api/notas-debito/',                api_notas_debito,       name='api_notas_debito'),
    path('api/guias-remision/',              api_guias_remision,     name='api_guias_remision'),
    path('api/comprobantes/buscar/',         buscar_comprobante,     name='buscar_comprobante'),
]
