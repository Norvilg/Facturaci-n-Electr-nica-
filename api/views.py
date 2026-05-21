from rest_framework import generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.models import User, Group
from django.db import transaction
from django.shortcuts import render
from .serializers import (
    CustomTokenObtainPairSerializer,
    UsuarioSerializer,
    UsuarioPerfilSerializer,
    GrupoSerializer,
)
from .permissions import EsAdmin


# ── Login ─────────────────────────────────────────────────────────────────────
def login_page(request):
    return render(request, 'login.html')


class LoginView(TokenObtainPairView):
    """POST /api/auth/login/"""
    serializer_class   = CustomTokenObtainPairSerializer
    permission_classes = [AllowAny]


# ── Logout ────────────────────────────────────────────────────────────────────

class LogoutView(APIView):
    """POST /api/auth/logout/ — invalida el refresh token"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            refresh = request.data.get('refresh')
            if not refresh:
                return Response({'error': 'Se requiere refresh token'},
                                status=status.HTTP_400_BAD_REQUEST)
            RefreshToken(refresh).blacklist()
            return Response({'mensaje': 'Sesión cerrada correctamente'})
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


# ── Perfil ────────────────────────────────────────────────────────────────────

class PerfilView(APIView):
    """GET/PUT /api/auth/perfil/"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UsuarioPerfilSerializer(request.user).data)

    def put(self, request):
        s = UsuarioSerializer(request.user, data=request.data,
                              partial=True, context={'request': request})
        if s.is_valid():
            s.save()
            return Response(UsuarioPerfilSerializer(request.user).data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Verificar token ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def verificar_token(request):
    """GET /api/auth/verificar/"""
    perfil = getattr(request.user, 'perfil', None)
    grupo  = request.user.groups.first()
    return Response({
        'valido':    True,
        'id':        request.user.id,
        'username':  request.user.username,
        'nombre':    request.user.get_full_name() or request.user.username,
        'rol':       grupo.name if grupo else None,
        'emisor_id': perfil.emisor_id if perfil else None,
    })


# ── CRUD usuarios (solo admin) ─────────────────────────────────────────────────

class UsuarioListCreateView(generics.ListCreateAPIView):
    """GET/POST /api/auth/usuarios/"""
    serializer_class   = UsuarioSerializer
    permission_classes = [IsAuthenticated, EsAdmin]

    def get_queryset(self):
        qs  = User.objects.prefetch_related('groups', 'perfil').order_by('username')
        rol = self.request.query_params.get('rol')
        if rol:
            qs = qs.filter(groups__name=rol)
        return qs


class UsuarioDetailView(generics.RetrieveUpdateDestroyAPIView):
    """GET/PUT/DELETE /api/auth/usuarios/{id}/"""
    serializer_class   = UsuarioSerializer
    permission_classes = [IsAuthenticated, EsAdmin]
    queryset           = User.objects.prefetch_related('groups', 'perfil')

    def destroy(self, request, *args, **kwargs):
        usuario = self.get_object()
        usuario.is_active = False
        usuario.save()
        return Response({'mensaje': f'Usuario {usuario.username} desactivado'})


# ── Grupos (roles) ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, EsAdmin])
def lista_grupos(request):
    """GET /api/auth/grupos/ — lista los grupos disponibles"""
    grupos = Group.objects.all()
    return Response(GrupoSerializer(grupos, many=True).data)
