from django import template

from facturacion.auth_utils import usuario_tiene_permiso

register = template.Library()


@register.filter
def tiene_permiso(user, codename):
    return usuario_tiene_permiso(user, codename)


@register.filter
def puede_emitir(user):
    from facturacion.roles import (
        PERM_EMIT_BOLETA,
        PERM_EMIT_FACTURA,
        PERM_EMIT_GUIA,
        PERM_EMIT_NC,
        PERM_EMIT_ND,
    )

    return any(
        usuario_tiene_permiso(user, p)
        for p in (
            PERM_EMIT_FACTURA,
            PERM_EMIT_BOLETA,
            PERM_EMIT_NC,
            PERM_EMIT_ND,
            PERM_EMIT_GUIA,
        )
    )
