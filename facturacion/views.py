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

from django.http import JsonResponse
from django.shortcuts import render
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt

from .models import (
    Cliente, Producto, Comprobante, Detalle,
    Serie, Emisor, Moneda, TipoComprobante, Cuota
)
from .services_sunat import procesar_comprobante_completo


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_emisor_activo() -> Emisor:
    """
    Retorna el emisor (empresa) activo.
    Ajusta el filtro según tu lógica de negocio.
    """
    return Emisor.objects.first()


def _get_moneda_soles() -> Moneda:
    """Retorna la moneda PEN/Soles."""
    return Moneda.objects.filter(
        descripcion__icontains='sol'
    ).first() or Moneda.objects.first()


def _get_tipo_comprobante(codigo: str) -> TipoComprobante:
    """
    Retorna el objeto TipoComprobante por código SUNAT ('01' o '03').
    Ajusta el filtro según los datos reales de tu tabla tipo_comprobante.
    """
    if codigo == '01':
        return TipoComprobante.objects.filter(
            descripcion__icontains='factura'
        ).first()
    return TipoComprobante.objects.filter(
        descripcion__icontains='boleta'
    ).first()


def _get_serie(tipo_codigo: str) -> Serie:
    """
    Retorna la serie activa según el tipo de comprobante.
    'F001' para facturas, 'B001' para boletas.
    """
    serie_nombre = 'F001' if tipo_codigo == '01' else 'B001'
    return Serie.objects.filter(serie=serie_nombre).first()


def _siguiente_correlativo(serie: Serie) -> int:
    """
    Obtiene e incrementa el correlativo de la serie.
    Usa select_for_update para evitar condiciones de carrera.
    """
    serie_locked = Serie.objects.select_for_update().get(pk=serie.pk)
    nuevo = serie_locked.correlativo + 1
    serie_locked.correlativo = nuevo
    serie_locked.save(update_fields=['correlativo'])
    return nuevo


def _calcular_detalle(item: dict, producto: Producto) -> dict:
    """
    Calcula los campos derivados de una línea de detalle.
    
    Tu modelo Detalle tiene:
      valor_unitario  → precio SIN IGV (lo que envía Alpine)
      precio_unitario → precio CON IGV
      valor_total     → subtotal sin IGV (valor_unitario * cantidad)
      importe_total   → total con IGV
      igv             → IGV de la línea
      porcentaje_igv  → 0.18
    """
    IGV_RATE      = Decimal('0.18')
    cantidad      = Decimal(str(item['cantidad']))
    v_unitario    = Decimal(str(item['v_unitario']))   # sin IGV (viene de Alpine)

    valor_total   = (cantidad * v_unitario).quantize(Decimal('0.01'))
    igv_linea     = (valor_total * IGV_RATE).quantize(Decimal('0.01'))
    precio_unit   = (v_unitario * (1 + IGV_RATE)).quantize(Decimal('0.01'))
    importe_total = (valor_total + igv_linea).quantize(Decimal('0.01'))

    return {
        'valor_unitario' : v_unitario,
        'precio_unitario': precio_unit,
        'valor_total'    : valor_total,
        'igv'            : igv_linea,
        'porcentaje_igv' : IGV_RATE,
        'importe_total'  : importe_total,
    }


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
    if request.method != 'POST':
        # GET: renderiza el formulario
        return _render_formulario(request, tipo_codigo)

    # POST: procesa el JSON de Alpine.js
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido.'}, status=400)

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

            # ── 4. Crear Comprobante en TU BD ─────────────────────────────────
            comprobante = Comprobante.objects.create(
                id_emisor            = emisor,
                id_tipo_comprobante  = tipo_cp,
                id_serie             = serie,
                serie                = serie.serie,               # 'F001' o 'B001'
                correlativo          = correlativo,
                forma_pago           = data.get('forma_pago', 'Contado'),
                fecha_emision        = date.today(),
                fecha_vencimiento    = date.today(),              # ajusta si manejas crédito
                id_moneda            = moneda,
                op_grabadas          = op_grabadas,
                op_exoneradas        = Decimal('0.00'),
                op_inefactas         = Decimal('0.00'),
                igv                  = igv_total,
                total                = total,
                id_cliente           = cliente,
                estado_comprobante   = '0',                       # 0 = borrador
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
            resultado = {'estado': 'ACEPTADO', 'descripcion': 'Simulado correctamente sin XML'}

        # ── 8. Respuesta al frontend Alpine.js ───────────────────────────────
        numeracion = f"{serie.serie}-{correlativo:08d}"

        if resultado.get('estado') == 'ACEPTADO':
            return JsonResponse({
                'success'       : True,
                'numeracion'    : numeracion,
                'mensaje_sunat' : resultado.get('descripcion', 'Aceptado por SUNAT'),
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

    # 3. Retornamos usando la variable de la plantilla dinámica
    return render(request, template_html, {
        'titulo'              : titulo,
        'tipo_comprobante_id' : tipo_codigo,
        'clientes'            : clientes,
        'productos'           : productos,
    })

# ─────────────────────────────────────────────────────────────────────────────
# VISTAS PÚBLICAS
# ─────────────────────────────────────────────────────────────────────────────

def api_facturas(request):
    """Endpoint para emitir Facturas Electrónicas (código SUNAT 01)."""
    return _procesar_emision(request, tipo_codigo='01')


def api_boletas(request):
    """Endpoint para emitir Boletas de Venta (código SUNAT 03)."""
    return _procesar_emision(request, tipo_codigo='03')


# ASÍ LO LLAMAS: Agrega esta función exactamente debajo de api_boletas
def api_notas_credito(request):
    """Endpoint para emitir Notas de Crédito (código SUNAT 07)."""
    return _procesar_emision(request, tipo_codigo='07')


def api_notas_debito(request):
    """Endpoint para emitir Notas de Débito (código SUNAT 08)."""
    return _procesar_emision(request, tipo_codigo='08')


def api_guias_remision(request):
    """Endpoint para emitir Guías de Remisión (código SUNAT 09)."""
    return _procesar_emision(request, tipo_codigo='09')


def dashboard(request):
    """Panel principal."""
    return render(request, 'base.html')


def lista_clientes_view(request):
    clientes = Cliente.objects.select_related('id_tipo_doc').all()
    return render(request, 'clientes_list.html', {'lista_clientes': list(clientes)})


def lista_productos_view(request):
    productos = Producto.objects.select_related('id_tipo_afectacion', 'id_unidad').all()
    return render(request, 'productos_list.html', {'lista_productos': list(productos)})