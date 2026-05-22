"""
views.py — SISTEMAFACTURACION/facturacion/views.py
===================================================
Vista actualizada que:
1. Recibe el JSON de Alpine.js
2. Guarda en TU BD (tus modelos)
3. Llama al adaptador → services.py del compañero → SUNAT
"""

import json
from datetime import date
from decimal import Decimal
from functools import wraps

from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import logout as django_logout
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import (
    Cliente, Producto, Comprobante, Detalle,
    Serie, Emisor, Moneda, TipoComprobante, Cuota
)

from .auth_utils import permiso_requerido, usuario_tiene_permiso
from .roles import (
    PERM_BUSCAR,
    PERM_CONSULTAR,
    PERM_DASHBOARD,
    PERM_EMIT_BOLETA,
    PERM_EMIT_FACTURA,
    PERM_EMIT_GUIA,
    PERM_EMIT_NC,
    PERM_EMIT_ND,
    PERM_VER_PERFIL,
    PERMISO_POR_TIPO_SUNAT,
)
from .services_sunat import procesar_comprobante_completo
from .calculos_tributarios import calcular_linea_detalle, calcular_totales_desde_total_con_igv
from .numeracion import siguiente_correlativo as _siguiente_correlativo_serie


# ─────────────────────────────────────────────────────────────────────────────
# CONTROL DE ROLES
# ─────────────────────────────────────────────────────────────────────────────

def _get_rol(request) -> str:
    """Retorna el rol del usuario autenticado: 'admin', 'emisor', 'contador' o ''."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return ''
    if user.is_superuser:
        return 'admin'
    grupo = user.groups.first()
    return grupo.name if grupo else ''


def _es_admin(request):
    return _get_rol(request) == 'admin'


def _es_emisor(request):
    return _get_rol(request) in ('admin', 'emisor')


def _es_contador(request):
    return _get_rol(request) in ('admin', 'contador')


def solo_roles(*roles):
    """
    Decorador que restringe una vista a los roles indicados.
    Uso: @solo_roles('admin', 'emisor')
    Si el usuario no tiene el rol → redirige a dashboard con error 403.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            rol = _get_rol(request)
            if rol not in roles:
                return render(request, 'facturacion/dashboard.html', {
                    'error_permiso': f'No tienes permiso para acceder a esta sección. Rol requerido: {" o ".join(roles)}.',
                }, status=403)
            return func(request, *args, **kwargs)
        return wrapper
    return decorator

def _get_emisor_activo() -> Emisor:
    """
    Retorna el emisor (empresa) activo.
    Ajusta el filtro según tu lógica de negocio.
    """
    return Emisor.objects.first()


def _get_moneda_soles() -> Moneda:
    """Retorna la moneda PEN/Soles."""
    # Intentamos buscar por descripción que contenga 'sol'
    moneda = Moneda.objects.filter(descripcion__icontains='sol').first()
    if moneda:
        return moneda
        
    # Si no la encuentra, intentamos buscar por el código estándar 'PEN'
    moneda_pen = Moneda.objects.filter(id_moneda='PEN').first() # ajusta si el campo se llama código
    if moneda_pen:
        return moneda_pen

    # Como último recurso para evitar el NULL, retornamos el primer registro que exista en la tabla
    return Moneda.objects.first()


def _get_tipo_comprobante(codigo: str) -> TipoComprobante:
    """Retorna TipoComprobante según código SUNAT (01, 03, 07, 08, 09)."""
    palabras_por_codigo = {
        '01': ('factura',),
        '03': ('boleta',),
        '07': ('crédito', 'credito'),
        '08': ('débito', 'debito'),
        '09': ('guía', 'guia', 'remisión', 'remision'),
    }
    palabras = palabras_por_codigo.get(codigo, ('boleta',))
    filtro = Q()
    for palabra in palabras:
        filtro |= Q(descripcion__icontains=palabra)
    return TipoComprobante.objects.filter(filtro).first()


def _get_serie(tipo_codigo: str) -> Serie:
    """Retorna la serie activa según el tipo de comprobante."""
    series_preferidas = {
        '01': 'F001',
        '03': 'B001',
        '07': 'FC01',
        '08': 'FD01',
        '09': 'T001',
    }
    serie_nombre = series_preferidas.get(tipo_codigo)
    if serie_nombre:
        serie = Serie.objects.filter(serie=serie_nombre).first()
        if serie:
            return serie
    return Serie.objects.first()


def _detalles_comprobante_dict(comp) -> list:
    """Líneas del comprobante referenciado para el formulario de notas."""
    return [
        {
            'id_producto': det.id_producto_id,
            'nombre': det.id_producto.nombre,
            'cantidad': str(det.cantidad),
            'valor_unitario': str(det.valor_unitario),
            'subtotal': str(det.valor_total),
        }
        for det in (
            Detalle.objects
            .filter(id_comprobante=comp)
            .select_related('id_producto')
            .order_by('item')
        )
    ]


def _comprobante_a_dict(comp) -> dict:
    """Serializa un comprobante aceptado para el frontend."""
    tipo_desc = (comp.id_tipo_comprobante.descripcion or '') if comp.id_tipo_comprobante else ''
    tipo_lower = tipo_desc.lower()
    if 'boleta' in tipo_lower:
        tipo_codigo = '03'
    elif 'factura' in tipo_lower:
        tipo_codigo = '01'
    else:
        tipo_codigo = '01'

    return {
        'encontrado': True,
        'id': comp.id_comprobante,
        'numeracion': f'{comp.serie}-{comp.correlativo:08d}',
        'serie': comp.serie,
        'correlativo': comp.correlativo,
        'tipo_codigo': tipo_codigo,
        'tipo_display': tipo_desc,
        'estado': comp.estado_comprobante,
        'cliente_id': comp.id_cliente_id,
        'cliente': comp.id_cliente.razon_social,
        'cliente_doc': comp.id_cliente.nrodoc,
        'direccion': comp.id_cliente.direccion or '',
        'fecha': comp.fecha_emision.isoformat(),
        'op_grabadas': str(comp.op_grabadas),
        'igv': str(comp.igv),
        'total': str(comp.total),
        'detalles': _detalles_comprobante_dict(comp),
    }


def _enriquecer_payload_nota(data: dict) -> dict:
    """
    Completa cliente_id, totales e items cuando el formulario de NC/ND
    envía solo comprobante_id, tipo y monto_afectado.
    """
    data = dict(data)
    ref_comp = None

    if data.get('comprobante_id'):
        ref_comp = (
            Comprobante.objects
            .filter(pk=data['comprobante_id'], estado_comprobante='1')
            .select_related('id_cliente', 'id_tipo_comprobante')
            .first()
        )
        if not ref_comp:
            raise ValueError('Comprobante referenciado no encontrado o no está ACEPTADO.')

    if not data.get('cliente_id'):
        if ref_comp:
            data['cliente_id'] = ref_comp.id_cliente_id
        else:
            raise ValueError('Falta cliente_id o comprobante_id.')

    if 'totales' not in data or not data['totales']:
        try:
            totales_nc = calcular_totales_desde_total_con_igv(data.get('monto_afectado', 0))
        except ValueError as exc:
            raise ValueError('Ingrese un monto afectado válido.') from exc
        data['totales'] = {
            'op_grabadas': str(totales_nc['op_grabadas']),
            'igv': str(totales_nc['igv']),
            'total': str(totales_nc['total']),
        }

    if not data.get('items'):
        op_linea = Decimal(str(data['totales']['op_grabadas']))
        producto_id = None
        if ref_comp:
            primer_det = (
                Detalle.objects
                .filter(id_comprobante=ref_comp)
                .order_by('item')
                .values_list('id_producto_id', flat=True)
                .first()
            )
            producto_id = primer_det
        if not producto_id:
            producto_id = Producto.objects.order_by('id_producto').values_list(
                'id_producto', flat=True
            ).first()
        if not producto_id:
            raise ValueError('No hay productos en catálogo para generar el detalle de la nota.')
        data['items'] = [{
            'id': producto_id,
            'cantidad': 1,
            'v_unitario': str(op_linea),
        }]

    if not data.get('codmotivo'):
        data['codmotivo'] = data.get('tipo_nota') or data.get('tipo_sustento') or ''

    if not data.get('comprobante_ref') and ref_comp:
        data['comprobante_ref'] = _comprobante_a_dict(ref_comp)

    data.setdefault('forma_pago', 'Contado')
    return data


def _siguiente_correlativo(serie: Serie) -> int:
    """Delega en facturacion.numeracion (tests de numeración)."""
    return _siguiente_correlativo_serie(serie)


def _calcular_detalle(item: dict, producto: Producto) -> dict:
    """Delega en facturacion.calculos_tributarios (tests de IGV)."""
    return calcular_linea_detalle(item['cantidad'], item['v_unitario'])


# ─────────────────────────────────────────────────────────────────────────────
# LÓGICA COMÚN DE EMISIÓN (factura y boleta comparten el mismo flujo)
# ─────────────────────────────────────────────────────────────────────────────

def _procesar_emision(request, tipo_codigo: str):
    """
    Lógica compartida para emitir factura (01) o boleta (03).
    
    Parámetros
    ----------
    tipo_codigo : '01' para factura, '03' para boleta
    """
    perm_codigo = PERMISO_POR_TIPO_SUNAT.get(tipo_codigo)
    if perm_codigo and not usuario_tiene_permiso(request.user, perm_codigo):
        if request.method == 'POST':
            return JsonResponse(
                {'success': False, 'error': 'No tiene permiso para emitir este comprobante.'},
                status=403,
            )
        from django.shortcuts import render
        from .auth_utils import nombre_rol_usuario
        return render(
            request,
            '403.html',
            {'permiso_requerido': perm_codigo, 'rol_usuario': nombre_rol_usuario(request.user)},
            status=403,
        )

    if request.method != 'POST':
        # GET: renderiza el formulario
        return _render_formulario(request, tipo_codigo)

    # POST: procesa el JSON de Alpine.js
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido.'}, status=400)

    if tipo_codigo in ('01', '03'):
        tipo_enviado = str(data.get('tipo_comprobante') or '')
        if tipo_enviado and tipo_enviado != tipo_codigo:
            esperado = 'FACTURA' if tipo_codigo == '01' else 'BOLETA'
            return JsonResponse({
                'success': False,
                'error': f'El tipo de comprobante no coincide. Use la pantalla de {esperado}.',
            }, status=400)

    if tipo_codigo in ('07', '08'):
        try:
            data = _enriquecer_payload_nota(data)
        except ValueError as exc:
            return JsonResponse({'success': False, 'error': str(exc)}, status=400)

    try:
        with transaction.atomic():

            # ── 1. Obtener objetos de BD ──────────────────────────────────────
            cliente = Cliente.objects.get(pk=data['cliente_id'])
            emisor  = _get_emisor_activo()
            moneda  = _get_moneda_soles()
            tipo_cp = _get_tipo_comprobante(tipo_codigo)
            serie   = _get_serie(tipo_codigo)

            if not emisor:
                return JsonResponse({'success': False, 'error': 'No hay emisor configurado.'})
            if not serie:
                return JsonResponse({'success': False, 'error': f'No existe la serie para tipo {tipo_codigo}.'})

            # ── 2. Correlativo ────────────────────────────────────────────────
            correlativo = _siguiente_correlativo(serie)

            # ── 3. Totales del comprobante ────────────────────────────────────
            op_grabadas = Decimal(str(data['totales']['op_grabadas']))
            igv_total   = Decimal(str(data['totales']['igv']))
            total       = Decimal(str(data['totales']['total']))

            # Referencia a comprobante original (notas de crédito / débito)
            ref = data.get('comprobante_ref') or {}
            if not ref and data.get('comprobante_id'):
                ref_comp = Comprobante.objects.filter(
                    pk=data['comprobante_id'],
                    estado_comprobante='1',
                ).select_related('id_tipo_comprobante').first()
                if ref_comp:
                    ref = _comprobante_a_dict(ref_comp)

            # ── 4. Crear Comprobante en TU BD ─────────────────────────────────
            comprobante = Comprobante.objects.create(
                id_emisor            = emisor,
                id_tipo_comprobante  = tipo_cp,
                id_serie             = serie,
                serie                = serie.serie,
                correlativo          = correlativo,
                forma_pago           = data.get('forma_pago', 'Contado'),
                fecha_emision        = date.today(),
                fecha_vencimiento    = date.today(),
                id_moneda            = moneda,
                op_grabadas          = op_grabadas,
                op_exoneradas        = Decimal('0.00'),
                op_inefactas         = Decimal('0.00'),
                igv                  = igv_total,
                total                = total,
                id_cliente           = cliente,
                estado_comprobante   = '0',
                tipo_comprobante_ref_id=ref.get('tipo_codigo') or data.get('tipo_comprobante_ref'),
                serie_ref            =ref.get('serie') or data.get('serie_ref'),
                correlativo_ref      =ref.get('correlativo') or data.get('correlativo_ref'),
                codmotivo            =data.get('codmotivo') or data.get('tipo_sustento'),
            )

            # ── 5. Crear Detalles en TU BD ────────────────────────────────────
            detalles_guardados = []
            for i, item in enumerate(data['items'], start=1):
                producto = Producto.objects.get(pk=item['id'])
                calc     = _calcular_detalle(item, producto)

                detalle = Detalle.objects.create(
                    id_comprobante   = comprobante,
                    item             = i,
                    id_producto      = producto,
                    cantidad         = Decimal(str(item['cantidad'])),
                    **calc
                )
                detalles_guardados.append(detalle)

            # ── 6. Guardar Cuotas si es crédito ───────────────────────────────
            if data.get('forma_pago') == 'Credito' and data.get('cuotas'):
                for idx, cuota_data in enumerate(data['cuotas'], start=1):
                    Cuota.objects.create(
                        id_comprobante   = comprobante,
                        numero           = str(idx).zfill(3),
                        importe          = Decimal(str(cuota_data['importe'])),
                        fecha_vencimiento= cuota_data['fecha'],
                        estado           = '0',
                    )

            # ── 7. Llamar al adaptador → Motor SUNAT del compañero ────────────
            #resultado = {'estado': 'ACEPTADO', 'descripcion': 'Simulado correctamente sin XML'}

            # 🔥 ACTIVAMOS EL ENVÍO REAL PASÁNDOLE LOS DATOS QUE ACABAMOS DE GUARDAR:
            resultado = procesar_comprobante_completo(comprobante, detalles_guardados)

        # ── 8. Respuesta al frontend Alpine.js ───────────────────────────────
        numeracion = f"{serie.serie}-{correlativo:08d}"

        if resultado.get('estado') == 'ACEPTADO':
            return JsonResponse({
                'success'        : True,
                'numeracion'     : numeracion,
                'comprobante_id' : comprobante.id_comprobante,
                'mensaje_sunat'  : resultado.get('descripcion', 'Aceptado por SUNAT'),
            })
        else:
            return JsonResponse({
                'success'       : False,
                'error'         : f"SUNAT rechazó el comprobante: {resultado.get('descripcion', 'Error desconocido')}",
                'codigo_sunat'  : resultado.get('codigo', ''),
            })

    except Cliente.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Cliente no encontrado.'}, status=404)
    except Producto.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Producto no encontrado.'}, status=404)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


def _render_formulario(request, tipo_codigo: str):
    """Renderiza el formulario HTML dinámico con datos de BD."""
    clientes  = Cliente.objects.all().order_by('razon_social')
    productos = Producto.objects.all().order_by('nombre')

    # 1. Conservas tu asignación de títulos intacta como te funciona hoy
    titulo = 'Emitir Factura Electrónica' if tipo_codigo == '01' else 'Emitir Boleta de Venta'

    # 2. DEFINIMOS QUÉ ARCHIVO HTML CARGAR SEGÚN EL CÓDIGO SUNAT
    if tipo_codigo == '01' or tipo_codigo == '03':
        template_html = 'facturacion/comprobante_form.html'  # Tu formulario actual de siempre
    elif tipo_codigo == '07':
        template_html = 'facturacion/nota_credito_form.html' # El nuevo HTML profesional de nota de crédito
    elif tipo_codigo == '08':
        template_html = 'facturacion/nota_debito_form.html'  # El nuevo HTML profesional de nota de débito
    elif tipo_codigo == '09':
        template_html = 'facturacion/guia_remision_form.html' # El nuevo HTML profesional de guía de remisión
    else:
        template_html = 'facturacion/comprobante_form.html'

    comprobantes_aceptados = (
        Comprobante.objects
        .filter(estado_comprobante='1')
        .exclude(id_tipo_comprobante__descripcion__icontains='crédito')
        .exclude(id_tipo_comprobante__descripcion__icontains='credito')
        .exclude(id_tipo_comprobante__descripcion__icontains='débito')
        .exclude(id_tipo_comprobante__descripcion__icontains='debito')
        .select_related('id_cliente', 'id_tipo_comprobante')
        .order_by('-fecha_emision', '-correlativo')[:100]
    )

    producto_default = productos.first()

    serie_emision = 'F001' if tipo_codigo == '01' else 'B001'
    correlativo_siguiente = 1
    tipo_comprobante_label = 'FACTURA' if tipo_codigo == '01' else 'BOLETA'
    if tipo_codigo in ('01', '03'):
        serie_obj = _get_serie(tipo_codigo)
        if serie_obj:
            serie_emision = serie_obj.serie
            correlativo_siguiente = serie_obj.correlativo + 1

    # 3. Retornamos usando la variable de la plantilla dinámica
    return render(request, template_html, {
        'titulo'              : titulo,
        'tipo_comprobante_id' : tipo_codigo,
        'tipo_comprobante_label': tipo_comprobante_label,
        'serie_emision': serie_emision,
        'correlativo_siguiente': correlativo_siguiente,
        'clientes'            : clientes,
        'productos'           : productos,
        'comprobantes_aceptados': comprobantes_aceptados,
        'producto_default_id': producto_default.id_producto if producto_default else None,
    })


@permiso_requerido(PERM_BUSCAR)
def buscar_comprobante(request):
    """API: busca factura/boleta aceptada por serie y correlativo (PostgreSQL)."""
    if request.method != 'GET':
        return JsonResponse({'encontrado': False, 'error': 'Método no permitido.'}, status=405)

    serie = (request.GET.get('serie') or '').strip().upper()
    numero = (request.GET.get('numero') or '').strip()

    if not serie or not numero:
        return JsonResponse({'encontrado': False, 'error': 'Serie y número son obligatorios.'})

    try:
        correlativo = int(numero)
    except ValueError:
        return JsonResponse({'encontrado': False, 'error': 'Número de comprobante inválido.'})

    comp = (
        Comprobante.objects
        .filter(serie=serie, correlativo=correlativo, estado_comprobante='1')
        .select_related('id_cliente', 'id_tipo_comprobante')
        .first()
    )

    if not comp:
        return JsonResponse({
            'encontrado': False,
            'error': 'Comprobante no encontrado o no está ACEPTADO por SUNAT.',
        })

    return JsonResponse(_comprobante_a_dict(comp))

# ─────────────────────────────────────────────────────────────────────────────
# VISTAS PÚBLICAS
# ─────────────────────────────────────────────────────────────────────────────

<<<<<<< HEAD
@solo_roles('admin', 'emisor')
=======
@permiso_requerido(PERM_EMIT_FACTURA)
>>>>>>> edin
def api_facturas(request):
    """Endpoint para emitir Facturas Electrónicas (código SUNAT 01)."""
    return _procesar_emision(request, tipo_codigo='01')


<<<<<<< HEAD
@solo_roles('admin', 'emisor')
=======
@permiso_requerido(PERM_EMIT_BOLETA)
>>>>>>> edin
def api_boletas(request):
    """Endpoint para emitir Boletas de Venta (código SUNAT 03)."""
    return _procesar_emision(request, tipo_codigo='03')


<<<<<<< HEAD
@solo_roles('admin', 'emisor')
=======
# ASÍ LO LLAMAS: Agrega esta función exactamente debajo de api_boletas
@permiso_requerido(PERM_EMIT_NC)
>>>>>>> edin
def api_notas_credito(request):
    """Endpoint para emitir Notas de Crédito (código SUNAT 07)."""
    return _procesar_emision(request, tipo_codigo='07')


<<<<<<< HEAD
@solo_roles('admin', 'emisor')
=======
@permiso_requerido(PERM_EMIT_ND)
>>>>>>> edin
def api_notas_debito(request):
    """Endpoint para emitir Notas de Débito (código SUNAT 08)."""
    return _procesar_emision(request, tipo_codigo='08')


<<<<<<< HEAD
@solo_roles('admin', 'emisor')
=======
@permiso_requerido(PERM_EMIT_GUIA)
>>>>>>> edin
def api_guias_remision(request):
    """Endpoint para emitir Guías de Remisión (código SUNAT 09)."""
    return _procesar_emision(request, tipo_codigo='09')


def _primer_dia_mes(d: date) -> date:
    return d.replace(day=1)


def _meses_atras(primer_dia: date, cantidad: int) -> date:
    """Primer día del mes `cantidad-1` meses antes de `primer_dia` (6 meses → 5 atrás)."""
    year, month = primer_dia.year, primer_dia.month - (cantidad - 1)
    while month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _siguiente_mes(primer_dia: date) -> date:
    if primer_dia.month == 12:
        return date(primer_dia.year + 1, 1, 1)
    return date(primer_dia.year, primer_dia.month + 1, 1)


def _ventas_aceptadas_chart(hoy: date, meses: int = 6):
    """
    Ventas aceptadas (estado 1) agrupadas por mes.
    Rellena meses sin ventas con 0 para que el gráfico se vea desde el primer aceptado.
    """
    fin_mes = _primer_dia_mes(hoy)
    inicio_rango = _meses_atras(fin_mes, meses)

    ventas_por_mes = (
        Comprobante.objects
        .filter(fecha_emision__gte=inicio_rango, estado_comprobante='1')
        .annotate(mes=TruncMonth('fecha_emision'))
        .values('mes')
        .annotate(monto=Sum('total'))
        .order_by('mes')
    )

    montos_por_mes = {}
    for fila in ventas_por_mes:
        mes_val = fila.get('mes')
        if not mes_val:
            continue
        clave = mes_val.date() if hasattr(mes_val, 'date') else mes_val
        if isinstance(clave, date):
            clave = _primer_dia_mes(clave)
        montos_por_mes[clave] = float(fila['monto'] or 0)

    labels = []
    montos = []
    cursor = inicio_rango
    while cursor <= fin_mes:
        labels.append(cursor.strftime('%b %Y'))
        montos.append(montos_por_mes.get(cursor, 0.0))
        cursor = _siguiente_mes(cursor)

    tiene_datos = any(m > 0 for m in montos)
    return labels, montos, tiene_datos


def _contar_comprobantes_por_tipo(*palabras_clave: str) -> int:
    """Cuenta comprobantes cuyo tipo contiene alguna de las palabras clave."""
    if not palabras_clave:
        return 0
    filtro = Q()
    for palabra in palabras_clave:
        filtro |= Q(id_tipo_comprobante__descripcion__icontains=palabra)
    return Comprobante.objects.filter(filtro).count()


@permiso_requerido(PERM_DASHBOARD)
def dashboard(request):
    """Panel principal con indicadores de la rúbrica del docente."""
    hoy = timezone.now().date()
    inicio_mes = hoy.replace(day=1)

    total_clientes = Cliente.objects.count()
    total_productos = Producto.objects.count()
    total_comprobantes = Comprobante.objects.count()
    aceptados = Comprobante.objects.filter(estado_comprobante='1').count()
    rechazados = Comprobante.objects.filter(estado_comprobante='2').count()
    pendientes = Comprobante.objects.filter(
        Q(estado_comprobante='0') | Q(estado_comprobante__isnull=True)
    ).count()

    comprobantes_mes = Comprobante.objects.filter(fecha_emision__gte=inicio_mes)
    facturas_mes = comprobantes_mes.filter(
        id_tipo_comprobante__descripcion__icontains='factura'
    ).count()
    boletas_mes = comprobantes_mes.filter(
        id_tipo_comprobante__descripcion__icontains='boleta'
    ).count()

    ventas_mes = Comprobante.objects.filter(
        fecha_emision__gte=inicio_mes,
        estado_comprobante='1',
    ).aggregate(total=Sum('total'))['total'] or 0

    emisor = Emisor.objects.first()

    por_tipo = {
        'facturas': _contar_comprobantes_por_tipo('factura'),
        'boletas': _contar_comprobantes_por_tipo('boleta'),
        'notas_credito': _contar_comprobantes_por_tipo('crédito', 'credito'),
        'notas_debito': _contar_comprobantes_por_tipo('débito', 'debito'),
        'guias': _contar_comprobantes_por_tipo('guía', 'guia', 'remisión', 'remision'),
    }

    ultimos_comprobantes = (
        Comprobante.objects
        .select_related('id_cliente', 'id_tipo_comprobante')
        .order_by('-fecha_emision', '-correlativo')[:8]
    )

    chart_labels, chart_montos, chart_has_data = _ventas_aceptadas_chart(hoy)

    modulos_todos = [
        {
            'nombre': 'Factura electrónica',
            'codigo': '01',
            'url': 'api_facturas',
            'icono': 'bi-file-earmark-text',
            'cantidad': por_tipo['facturas'],
            'permiso': PERM_EMIT_FACTURA,
        },
        {
            'nombre': 'Boleta de venta',
            'codigo': '03',
            'url': 'api_boletas',
            'icono': 'bi-receipt',
            'cantidad': por_tipo['boletas'],
            'permiso': PERM_EMIT_BOLETA,
        },
        {
            'nombre': 'Nota de crédito',
            'codigo': '07',
            'url': 'api_notas_credito',
            'icono': 'bi-file-earmark-minus',
            'cantidad': por_tipo['notas_credito'],
            'permiso': PERM_EMIT_NC,
        },
        {
            'nombre': 'Nota de débito',
            'codigo': '08',
            'url': 'api_notas_debito',
            'icono': 'bi-file-earmark-plus',
            'cantidad': por_tipo['notas_debito'],
            'permiso': PERM_EMIT_ND,
        },
        {
            'nombre': 'Guía de remisión',
            'codigo': '09',
            'url': 'api_guias_remision',
            'icono': 'bi-truck',
            'cantidad': por_tipo['guias'],
            'permiso': PERM_EMIT_GUIA,
        },
    ]
    modulos_docente = [
        m for m in modulos_todos
        if usuario_tiene_permiso(request.user, m['permiso'])
    ]

    return render(request, 'facturacion/dashboard.html', {
        'total_clientes': total_clientes,
        'total_productos': total_productos,
        'total_comprobantes': total_comprobantes,
        'facturas_mes': facturas_mes,
        'boletas_mes': boletas_mes,
        'aceptados': aceptados,
        'rechazados': rechazados,
        'pendientes': pendientes,
        'alertas_sunat': rechazados + pendientes,
        'ventas_mes': ventas_mes,
        'emisor': emisor,
        'modulos_docente': modulos_docente,
        'ultimos_comprobantes': ultimos_comprobantes,
        'chart_labels': chart_labels,
        'chart_has_data': chart_has_data,
        'chart_labels_json': json.dumps(chart_labels, ensure_ascii=False),
        'chart_montos_json': json.dumps(chart_montos),
    })


<<<<<<< HEAD
@solo_roles('admin')
=======
@permiso_requerido(PERM_VER_PERFIL)
>>>>>>> edin
def perfil_emisor_view(request):
    """Perfil / datos del emisor (botón Perfil del menú superior)."""
    emisor = Emisor.objects.first()
    return render(request, 'facturacion/perfil_emisor.html', {'emisor': emisor})


<<<<<<< HEAD
def lista_clientes_view(request):
    clientes = Cliente.objects.select_related('id_tipo_doc').all()
    return render(request, 'clientes_list.html', {'lista_clientes': list(clientes)})
    
def lista_productos_view(request):
    productos = Producto.objects.select_related('id_tipo_afectacion', 'id_unidad').all()
    return render(request, 'productos_list.html', {'lista_productos': list(productos)})


=======
>>>>>>> edin
def _estado_comprobante_label(estado) -> str:
    return {
        '1': 'ACEPTADO',
        '2': 'RECHAZADO',
        '0': 'PENDIENTE',
    }.get(estado or '0', 'PENDIENTE')


def _titulo_ticket(comp) -> str:
    """Título centrado estilo ticket SUNAT."""
    desc = (comp.id_tipo_comprobante.descripcion or '').lower()
    if 'boleta' in desc:
        return 'BOLETA DE VENTA ELECTRONICA'
    if 'crédito' in desc or 'credito' in desc:
        return 'NOTA DE CREDITO ELECTRONICA'
    if 'débito' in desc or 'debito' in desc:
        return 'NOTA DE DEBITO ELECTRONICA'
    if 'guía' in desc or 'guia' in desc:
        return 'GUIA DE REMISION ELECTRONICA'
    return 'FACTURA ELECTRONICA'


def _tipo_codigo_sunat(comp) -> str:
    desc = (comp.id_tipo_comprobante.descripcion or '').lower()
    if 'boleta' in desc:
        return '03'
    if 'crédito' in desc or 'credito' in desc:
        return '07'
    if 'débito' in desc or 'debito' in desc:
        return '08'
    if 'guía' in desc or 'guia' in desc:
        return '09'
    return '01'


def _numero_a_letras_entero(n: int) -> str:
    """Convierte entero 0-999999 a letras (español)."""
    if n == 0:
        return 'CERO'
    unidades = (
        '', 'UN', 'DOS', 'TRES', 'CUATRO', 'CINCO', 'SEIS', 'SIETE', 'OCHO', 'NUEVE',
    )
    especiales = (
        'DIEZ', 'ONCE', 'DOCE', 'TRECE', 'CATORCE', 'QUINCE', 'DIECISEIS', 'DIECISIETE',
        'DIECIOCHO', 'DIECINUEVE',
    )
    decenas = (
        '', '', 'VEINTE', 'TREINTA', 'CUARENTA', 'CINCUENTA',
        'SESENTA', 'SETENTA', 'OCHENTA', 'NOVENTA',
    )
    centenas = (
        '', 'CIENTO', 'DOSCIENTOS', 'TRESCIENTOS', 'CUATROCIENTOS', 'QUINIENTOS',
        'SEISCIENTOS', 'SETECIENTOS', 'OCHOCIENTOS', 'NOVECIENTOS',
    )

    def bajo(num):
        if num < 10:
            return unidades[num]
        if num < 20:
            return especiales[num - 10]
        if num < 100:
            d, u = divmod(num, 10)
            if u == 0:
                return decenas[d]
            if d == 2:
                return 'VEINTI' + unidades[u]
            return decenas[d] + ' Y ' + unidades[u]
        if num == 100:
            return 'CIEN'
        c, r = divmod(num, 100)
        return (centenas[c] + (' ' + bajo(r) if r else '')).strip()

    partes = []
    millones, resto = divmod(n, 1_000_000)
    miles, resto = divmod(resto, 1000)
    if millones:
        partes.append(bajo(millones) + ' MILLON' + ('ES' if millones > 1 else ''))
    if miles:
        partes.append(('UN MIL' if miles == 1 else bajo(miles) + ' MIL').strip())
    if resto or not partes:
        partes.append(bajo(resto))
    return ' '.join(partes)


def _total_en_letras_soles(total) -> str:
    monto = Decimal(str(total)).quantize(Decimal('0.01'))
    entero = int(monto)
    centavos = int((monto - Decimal(entero)) * 100)
    return f'SON {_numero_a_letras_entero(entero)} CON {centavos:02d}/100 SOLES'


def _texto_qr_sunat(comp, emisor, cliente) -> str:
    """Cadena para QR (formato simplificado RUC|tipo|serie|número|IGV|total|fecha|...)."""
    fecha = comp.fecha_emision.strftime('%Y-%m-%d') if comp.fecha_emision else ''
    tipo_doc_cli = '6' if len((cliente.nrodoc or '')) == 11 else '1'
    return '|'.join([
        emisor.ruc or '',
        _tipo_codigo_sunat(comp),
        comp.serie or '',
        str(comp.correlativo or ''),
        str(comp.igv or '0'),
        str(comp.total or '0'),
        fecha,
        tipo_doc_cli,
        cliente.nrodoc or '',
    ])


@permiso_requerido(PERM_CONSULTAR)
def lista_comprobantes_view(request):
    """Listado de comprobantes con enlaces a impresión ticket / A4."""
    comprobantes = (
        Comprobante.objects
        .select_related('id_cliente', 'id_tipo_comprobante', 'id_emisor')
        .order_by('-fecha_emision', '-correlativo')[:200]
    )
    return render(request, 'facturacion/comprobantes_list.html', {
        'comprobantes': comprobantes,
    })


@permiso_requerido(PERM_CONSULTAR)
def imprimir_comprobante(request, pk: int):
    """Representación impresa: ticket 80 mm o hoja A4 (?formato=ticket|a4)."""
    comp = get_object_or_404(
        Comprobante.objects.select_related(
            'id_emisor',
            'id_cliente',
            'id_cliente__id_tipo_doc',
            'id_tipo_comprobante',
            'id_moneda',
        ),
        pk=pk,
    )
    detalles = (
        Detalle.objects
        .filter(id_comprobante=comp)
        .select_related('id_producto')
        .order_by('item')
    )
    formato = (request.GET.get('formato') or 'a4').lower()
    if formato not in ('ticket', 'a4'):
        formato = 'a4'

    ref_numeracion = None
    if comp.serie_ref and comp.correlativo_ref is not None:
        ref_numeracion = f'{comp.serie_ref}-{comp.correlativo_ref:08d}'

    emisor = comp.id_emisor
    cliente = comp.id_cliente
    titulo_ticket = _titulo_ticket(comp)
    numeracion_corta = f'{comp.serie} - {comp.correlativo}'
    qr_texto = _texto_qr_sunat(comp, emisor, cliente)
    consulta_url = request.build_absolute_uri(f'/comprobantes/{pk}/imprimir/?formato=ticket')

    return render(request, 'facturacion/comprobante_imprimir.html', {
        'comprobante': comp,
        'detalles': detalles,
        'emisor': emisor,
        'cliente': cliente,
        'formato': formato,
        'auto_print': request.GET.get('auto') == '1',
        'numeracion': f'{comp.serie}-{comp.correlativo:08d}',
        'numeracion_corta': numeracion_corta,
        'estado_label': _estado_comprobante_label(comp.estado_comprobante),
        'tipo_nombre': comp.id_tipo_comprobante.descripcion or 'Comprobante',
        'titulo_ticket': titulo_ticket,
        'total_letras': _total_en_letras_soles(comp.total),
        'qr_texto': qr_texto,
        'consulta_url': consulta_url,
        'icbper': Decimal('0.00'),
        'ref_numeracion': ref_numeracion,
        'url_ticket': request.build_absolute_uri(
            f'/comprobantes/{pk}/imprimir/?formato=ticket'
        ),
        'url_a4': request.build_absolute_uri(
            f'/comprobantes/{pk}/imprimir/?formato=a4'
        ),
    })


def logout_view(request):
    """
    Cierra la sesión web:
    1. Cierra la sesión de Django
    2. Borra la cookie access_token del JWT
    3. Redirige al login
    """
    django_logout(request)
    response = redirect('/login/')
    response.delete_cookie('access_token')
    response.delete_cookie('refresh_token')
    return response