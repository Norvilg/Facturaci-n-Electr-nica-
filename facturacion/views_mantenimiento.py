"""Mantenimiento de catálogos y libro de ventas (rúbrica docente)."""
import csv
from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.db import IntegrityError
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from .auth_utils import permiso_requerido, usuario_tiene_permiso
from .forms import ClienteForm, ProductoForm
from .models import Cliente, Comprobante, Producto, TipoDocumento
from .roles import (
    PERM_CLIENTES,
    PERM_CRUD_CLIENTES,
    PERM_CRUD_PRODUCTOS,
    PERM_LIBRO_VENTAS,
    PERM_PRODUCTOS,
)


def _puede_crud_clientes(user) -> bool:
    return usuario_tiene_permiso(user, PERM_CRUD_CLIENTES)


def _puede_crud_productos(user) -> bool:
    return usuario_tiene_permiso(user, PERM_CRUD_PRODUCTOS)


def _estado_label(estado) -> str:
    return {'1': 'Aceptado', '2': 'Rechazado', '0': 'Pendiente'}.get(estado or '0', 'Pendiente')


# ─── Clientes ───────────────────────────────────────────────────────────────

@permiso_requerido(PERM_CLIENTES)
def lista_clientes_view(request):
    q = (request.GET.get('q') or '').strip()
    clientes = Cliente.objects.select_related('id_tipo_doc').order_by('razon_social')
    if q:
        clientes = clientes.filter(
            Q(nrodoc__icontains=q) | Q(razon_social__icontains=q)
        )
    return render(request, 'clientes_list.html', {
        'lista_clientes': clientes,
        'busqueda': q,
        'puede_crud': _puede_crud_clientes(request.user),
    })


@permiso_requerido(PERM_CRUD_CLIENTES)
def cliente_crear_view(request):
    form = ClienteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Cliente registrado correctamente.')
        return redirect('lista_clientes')
    return render(request, 'cliente_form.html', {
        'form': form,
        'titulo': 'Nuevo cliente',
        'accion': 'crear',
    })


@permiso_requerido(PERM_CRUD_CLIENTES)
def cliente_editar_view(request, pk: int):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST or None, instance=cliente)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Cliente actualizado.')
        return redirect('cliente_detalle', pk=pk)
    return render(request, 'cliente_form.html', {
        'form': form,
        'titulo': f'Editar: {cliente.razon_social}',
        'accion': 'editar',
        'cliente': cliente,
    })


@permiso_requerido(PERM_CRUD_CLIENTES)
def cliente_eliminar_view(request, pk: int):
    cliente = get_object_or_404(Cliente, pk=pk)
    if request.method != 'POST':
        return redirect('cliente_detalle', pk=pk)
    try:
        nombre = cliente.razon_social
        cliente.delete()
        messages.success(request, f'Cliente "{nombre}" eliminado.')
        return redirect('lista_clientes')
    except IntegrityError:
        messages.error(
            request,
            'No se puede eliminar: el cliente tiene comprobantes emitidos.',
        )
        return redirect('cliente_detalle', pk=pk)


@permiso_requerido(PERM_CLIENTES)
def cliente_detalle_view(request, pk: int):
    cliente = get_object_or_404(Cliente.objects.select_related('id_tipo_doc'), pk=pk)
    comprobantes = (
        Comprobante.objects
        .filter(id_cliente=cliente)
        .select_related('id_tipo_comprobante')
        .order_by('-fecha_emision', '-correlativo')
    )
    totales = comprobantes.aggregate(
        base=Sum('op_grabadas'),
        igv=Sum('igv'),
        total=Sum('total'),
    )
    return render(request, 'cliente_detalle.html', {
        'cliente': cliente,
        'comprobantes': comprobantes,
        'total_comprobantes': comprobantes.count(),
        'suma_base': totales['base'] or Decimal('0'),
        'suma_igv': totales['igv'] or Decimal('0'),
        'suma_total': totales['total'] or Decimal('0'),
        'puede_crud': _puede_crud_clientes(request.user),
    })


# ─── Productos ──────────────────────────────────────────────────────────────

@permiso_requerido(PERM_PRODUCTOS)
def lista_productos_view(request):
    q = (request.GET.get('q') or '').strip()
    productos = Producto.objects.select_related(
        'id_tipo_afectacion', 'id_unidad'
    ).order_by('nombre')
    if q:
        productos = productos.filter(
            Q(nombre__icontains=q) | Q(codigo_sunat__icontains=q)
        )
    return render(request, 'productos_list.html', {
        'lista_productos': productos,
        'busqueda': q,
        'puede_crud': _puede_crud_productos(request.user),
    })


@permiso_requerido(PERM_CRUD_PRODUCTOS)
def producto_crear_view(request):
    form = ProductoForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Producto/servicio registrado.')
        return redirect('lista_productos')
    return render(request, 'producto_form.html', {
        'form': form,
        'titulo': 'Nuevo producto o servicio',
    })


@permiso_requerido(PERM_CRUD_PRODUCTOS)
def producto_editar_view(request, pk: int):
    producto = get_object_or_404(Producto, pk=pk)
    form = ProductoForm(request.POST or None, instance=producto)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Producto/servicio actualizado.')
        return redirect('lista_productos')
    return render(request, 'producto_form.html', {
        'form': form,
        'titulo': f'Editar: {producto.nombre}',
        'producto': producto,
    })


@permiso_requerido(PERM_CRUD_PRODUCTOS)
def producto_eliminar_view(request, pk: int):
    producto = get_object_or_404(Producto, pk=pk)
    if request.method != 'POST':
        return redirect('lista_productos')
    try:
        nombre = producto.nombre
        producto.delete()
        messages.success(request, f'"{nombre}" eliminado.')
    except IntegrityError:
        messages.error(
            request,
            'No se puede eliminar: el producto está en comprobantes emitidos.',
        )
    return redirect('lista_productos')


# ─── Libro de ventas ────────────────────────────────────────────────────────

def _periodo_desde_request(request):
    hoy = timezone.now().date()
    try:
        anio = int(request.GET.get('anio', hoy.year))
        mes = int(request.GET.get('mes', hoy.month))
        if mes < 1 or mes > 12:
            raise ValueError
    except (TypeError, ValueError):
        anio, mes = hoy.year, hoy.month
    ultimo_dia = monthrange(anio, mes)[1]
    inicio = date(anio, mes, 1)
    fin = date(anio, mes, ultimo_dia)
    return inicio, fin, anio, mes


@permiso_requerido(PERM_LIBRO_VENTAS)
def libro_ventas_view(request):
    inicio, fin, anio, mes = _periodo_desde_request(request)
    comprobantes = (
        Comprobante.objects
        .filter(fecha_emision__gte=inicio, fecha_emision__lte=fin)
        .select_related('id_cliente', 'id_tipo_comprobante')
        .order_by('fecha_emision', 'serie', 'correlativo')
    )
    totales = comprobantes.aggregate(
        base=Sum('op_grabadas'),
        igv=Sum('igv'),
        total=Sum('total'),
    )
    filas = [
        {
            'comp': c,
            'estado': _estado_label(c.estado_comprobante),
            'numero': f'{c.serie}-{c.correlativo:08d}',
            'tipo': c.id_tipo_comprobante.descripcion or '—',
            'cliente_doc': c.id_cliente.nrodoc,
            'cliente_nombre': c.id_cliente.razon_social,
            'base': c.op_grabadas,
            'igv': c.igv,
            'total': c.total,
        }
        for c in comprobantes
    ]
    meses = [
        (1, 'Enero'), (2, 'Febrero'), (3, 'Marzo'), (4, 'Abril'),
        (5, 'Mayo'), (6, 'Junio'), (7, 'Julio'), (8, 'Agosto'),
        (9, 'Septiembre'), (10, 'Octubre'), (11, 'Noviembre'), (12, 'Diciembre'),
    ]
    return render(request, 'facturacion/libro_ventas.html', {
        'filas': filas,
        'anio': anio,
        'mes': mes,
        'meses': meses,
        'anios': range(timezone.now().year - 2, timezone.now().year + 2),
        'inicio': inicio,
        'fin': fin,
        'totales': {
            'base': totales['base'] or Decimal('0'),
            'igv': totales['igv'] or Decimal('0'),
            'total': totales['total'] or Decimal('0'),
        },
        'cantidad': len(filas),
    })


@permiso_requerido(PERM_LIBRO_VENTAS)
def libro_ventas_exportar_view(request):
    inicio, fin, anio, mes = _periodo_desde_request(request)
    comprobantes = (
        Comprobante.objects
        .filter(fecha_emision__gte=inicio, fecha_emision__lte=fin)
        .select_related('id_cliente', 'id_tipo_comprobante')
        .order_by('fecha_emision', 'serie', 'correlativo')
    )
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = (
        f'attachment; filename="libro_ventas_{anio}_{mes:02d}.csv"'
    )
    response.write('\ufeff')
    writer = csv.writer(response)
    writer.writerow([
        'Fecha', 'Tipo', 'Serie', 'Correlativo', 'Estado',
        'Doc. Cliente', 'Cliente', 'Base imponible', 'IGV', 'Total',
    ])
    suma_base = suma_igv = suma_total = Decimal('0')
    for c in comprobantes:
        writer.writerow([
            c.fecha_emision.isoformat(),
            c.id_tipo_comprobante.descripcion or '',
            c.serie,
            c.correlativo,
            _estado_label(c.estado_comprobante),
            c.id_cliente.nrodoc,
            c.id_cliente.razon_social,
            c.op_grabadas,
            c.igv,
            c.total,
        ])
        suma_base += c.op_grabadas
        suma_igv += c.igv
        suma_total += c.total
    writer.writerow([])
    writer.writerow([
        'TOTALES', '', '', '', '', '', '',
        suma_base, suma_igv, suma_total,
    ])
    return response
