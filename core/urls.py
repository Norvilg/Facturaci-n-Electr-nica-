"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import path
from facturacion.views import (
    dashboard, lista_clientes_view, lista_productos_view, perfil_emisor_view,
    lista_comprobantes_view, imprimir_comprobante,
    api_facturas, api_boletas, api_notas_credito, api_notas_debito, api_guias_remision,
    buscar_comprobante,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', dashboard, name='dashboard'),  # <-- Ruta raíz principal
    path('clientes/', lista_clientes_view, name='lista_clientes'), # <-- Nueva Ruta
    path('productos/', lista_productos_view, name='lista_productos'), # <-- Nueva Ruta
    path('perfil/', perfil_emisor_view, name='perfil_emisor'),
    path('cerrar-sesion/', LogoutView.as_view(next_page='/'), name='logout'),

    # Endpoints exactos de la rúbrica del docente
    path('api/facturas/', api_facturas, name='api_facturas'),
    path('api/boletas/', api_boletas, name='api_boletas'),

    # LISTO: Esta es la nueva ruta que activa la Nota de Crédito
    path('api/notas-credito/', api_notas_credito, name='api_notas_credito'),
    # LISTO: Esta es la nueva ruta que activa la Nota de Débito
    path('api/notas-debito/', api_notas_debito, name='api_notas_debito'),
    # LISTO: Esta es la nueva ruta que activa la Guía de Remisión
    path('api/guias-remision/', api_guias_remision, name='api_guias_remision'),
    path('api/comprobantes/buscar/', buscar_comprobante, name='buscar_comprobante'),
    path('comprobantes/', lista_comprobantes_view, name='lista_comprobantes'),
    path('comprobantes/<int:pk>/imprimir/', imprimir_comprobante, name='imprimir_comprobante'),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.BASE_DIR / 'static',
    )

