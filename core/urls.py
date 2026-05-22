from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Auth JWT + login
    path('', include('api.urls')),

    # Facturación (dashboard, comprobantes, clientes, productos, etc.)
    path('', include('facturacion.urls')),
]

if settings.DEBUG:
    urlpatterns += static(
        settings.STATIC_URL,
        document_root=settings.BASE_DIR / 'static',
    )
