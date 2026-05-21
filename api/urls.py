from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import (
    LoginView,
    LogoutView,
    PerfilView,
    UsuarioListCreateView,
    UsuarioDetailView,
    verificar_token,
    login_page,
)

urlpatterns = [
    # Auth
    path('login/',    login_page,        name='login-page'),
    path('api/auth/login/', LoginView.as_view(), name='auth-login'),
    path('api/auth/logout/',   LogoutView.as_view(),        name='auth-logout'),
    path('api/auth/refresh/',  TokenRefreshView.as_view(),  name='auth-refresh'),
    path('api/auth/verificar/', verificar_token,            name='auth-verificar'),
    path('api/auth/perfil/',   PerfilView.as_view(),        name='auth-perfil'),

    # CRUD usuarios (solo admin)
    path('usuarios/',       UsuarioListCreateView.as_view(), name='usuario-list'),
    path('usuarios/<int:pk>/', UsuarioDetailView.as_view(), name='usuario-detail'),
]
