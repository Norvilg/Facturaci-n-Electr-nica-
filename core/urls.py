from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),

    # Auth JWT + login page
    path('', include('api.urls')),

    # Facturación (dashboard en '/', demás vistas)
    path('', include('facturacion.urls')),
]
