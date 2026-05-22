"""Contexto global para el layout (navbar, menú usuario)."""
from django.db.models import Q, Sum
from django.utils import timezone

from .auth_utils import nombre_rol_usuario, permisos_usuario
from .models import Cliente, Comprobante, Emisor, Producto


def layout_context(request):
    """Datos del emisor y contadores SUNAT para toda la interfaz."""
    emisor = Emisor.objects.first()
    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)

    comprobantes_mes = Comprobante.objects.filter(fecha_emision__gte=inicio_mes)
    aceptados_mes = comprobantes_mes.filter(estado_comprobante='1')

    facturas_mes = comprobantes_mes.filter(
        id_tipo_comprobante__descripcion__icontains='factura'
    ).count()
    boletas_mes = comprobantes_mes.filter(
        id_tipo_comprobante__descripcion__icontains='boleta'
    ).count()

    total_vendido_mes = aceptados_mes.aggregate(t=Sum('total'))['t'] or 0
    rechazados = Comprobante.objects.filter(estado_comprobante='2').count()
    pendientes = Comprobante.objects.filter(
        Q(estado_comprobante='0') | Q(estado_comprobante__isnull=True)
    ).count()
    aceptados_total = Comprobante.objects.filter(estado_comprobante='1').count()

    ultimos_nav = (
        Comprobante.objects
        .select_related('id_cliente')
        .order_by('-fecha_emision', '-correlativo')[:5]
    )

    user = getattr(request, 'user', None)
    perms = permisos_usuario(user) if user else {}

    return {
        'layout_emisor': emisor,
        'rol_usuario': nombre_rol_usuario(user) if user and user.is_authenticated else '',
        'permisos': perms,
        'nav_facturas_mes': facturas_mes,
        'nav_boletas_mes': boletas_mes,
        'nav_total_vendido_mes': total_vendido_mes,
        'nav_rechazados': rechazados,
        'nav_pendientes': pendientes,
        'nav_aceptados': aceptados_total,
        'nav_alertas': rechazados + pendientes,
        'nav_ultimos_comprobantes': ultimos_nav,
        'nav_total_clientes': Cliente.objects.count(),
        'nav_total_productos': Producto.objects.count(),
    }
