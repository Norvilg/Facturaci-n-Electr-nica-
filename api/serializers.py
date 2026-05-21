from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework import serializers
from django.contrib.auth.models import User, Group
from .models import PerfilUsuario


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    JWT con datos extra: rol (grupo) y emisor_id del perfil.
    """
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        perfil    = getattr(user, 'perfil', None)
        grupo     = user.groups.first()
        token['rol']       = grupo.name if grupo else None
        token['nombre']    = user.get_full_name() or user.username
        token['emisor_id'] = perfil.emisor_id if perfil else None
        return token

    def validate(self, attrs):
        data   = super().validate(attrs)
        perfil = getattr(self.user, 'perfil', None)
        grupo  = self.user.groups.first()
        data['usuario'] = {
            'id':        self.user.id,
            'username':  self.user.username,
            'nombre':    self.user.get_full_name() or self.user.username,
            'email':     self.user.email,
            'rol':       grupo.name if grupo else None,
            'emisor_id': perfil.emisor_id if perfil else None,
        }
        return data


class GrupoSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Group
        fields = ['id', 'name']


class PerfilSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PerfilUsuario
        fields = ['emisor']


class UsuarioSerializer(serializers.ModelSerializer):
    """Serializer completo para CRUD de usuarios (solo admin)."""
    password   = serializers.CharField(write_only=True, min_length=6, required=False)
    grupos     = GrupoSerializer(source='groups', many=True, read_only=True)
    grupo_id   = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), write_only=True, required=False, source='groups'
    )
    emisor_id  = serializers.SerializerMethodField()
    emisor_set = serializers.PrimaryKeyRelatedField(
        write_only=True, required=False,
        queryset=__import__('facturacion.models', fromlist=['Emisor']).Emisor.objects.all()
    )

    class Meta:
        model  = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email',
                  'is_active', 'date_joined', 'grupos', 'grupo_id',
                  'emisor_id', 'emisor_set', 'password']
        read_only_fields = ['id', 'date_joined', 'grupos', 'emisor_id']

    def get_emisor_id(self, obj):
        perfil = getattr(obj, 'perfil', None)
        return perfil.emisor_id if perfil else None

    def create(self, validated_data):
        password  = validated_data.pop('password', None)
        grupo     = validated_data.pop('groups', None)
        emisor    = validated_data.pop('emisor_set', None)
        user      = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        if grupo:
            user.groups.set([grupo])
        PerfilUsuario.objects.update_or_create(user=user, defaults={'emisor': emisor})
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        grupo    = validated_data.pop('groups', None)
        emisor   = validated_data.pop('emisor_set', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        if grupo is not None:
            instance.groups.set([grupo])
        if emisor is not None:
            PerfilUsuario.objects.update_or_create(
                user=instance, defaults={'emisor': emisor}
            )
        return instance


class UsuarioPerfilSerializer(serializers.ModelSerializer):
    """Solo lectura — perfil del usuario logueado."""
    rol          = serializers.SerializerMethodField()
    emisor_id    = serializers.SerializerMethodField()
    emisor_nombre = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email',
                  'rol', 'emisor_id', 'emisor_nombre', 'date_joined']

    def get_rol(self, obj):
        g = obj.groups.first()
        return g.name if g else None

    def get_emisor_id(self, obj):
        p = getattr(obj, 'perfil', None)
        return p.emisor_id if p else None

    def get_emisor_nombre(self, obj):
        p = getattr(obj, 'perfil', None)
        if p and p.emisor:
            return p.emisor.razon_social
        return None
