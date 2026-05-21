from django.urls import path
from .views import dashboard, lista_clientes_view, lista_productos_view, api_facturas, api_boletas, api_notas_credito, api_notas_debito, api_guias_remision

urlpatterns = [
    path('', dashboard, name='dashboard'),
    path('clientes/', lista_clientes_view, name='lista_clientes'),
    path('productos/', lista_productos_view, name='lista_productos'),
    path('api/facturas/', api_facturas, name='api_facturas'),
    path('api/boletas/', api_boletas, name='api_boletas'),
    path('api/notas-credito/', api_notas_credito, name='api_notas_credito'),
    path('api/notas-debito/', api_notas_debito, name='api_notas_debito'),
    path('api/guias-remision/', api_guias_remision, name='api_guias_remision'),
]
