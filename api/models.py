from django.contrib.auth.models import User
from django.db import models


class PerfilUsuario(models.Model):
    """
    Extiende auth_user de Django sin reemplazarlo.
    Agrega solo lo que Django no tiene: FK al emisor (empresa).
    El rol se maneja con auth_group: admin | emisor | contador
    """
    user   = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    emisor = models.ForeignKey(
        'facturacion.Emisor',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='usuarios',
        help_text='Empresa a la que pertenece este usuario'
    )

    class Meta:
        db_table = 'perfil_usuario'
        verbose_name = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuarios'

    def __str__(self):
        return f"{self.user.username} → {self.emisor}"

    @property
    def rol(self):
        """Retorna el nombre del primer grupo del usuario (admin/emisor/contador)."""
        grupo = self.user.groups.first()
        return grupo.name if grupo else None

    @property
    def es_admin(self):
        return self.user.groups.filter(name='admin').exists()

    @property
    def es_emisor(self):
        return self.user.groups.filter(name='emisor').exists()

    @property
    def es_contador(self):
        return self.user.groups.filter(name='contador').exists()
