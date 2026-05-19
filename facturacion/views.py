from django.shortcuts import render
from .models import Cliente, Producto  # <-- Asegúrate de tener la importación


import json
from django.http import JsonResponse
from django.shortcuts import render
from django.db import transaction
from .models import Cliente, Producto, Comprobante, Detalle, Serie, Emisor, Moneda

def dashboard(request):
    return render(request, 'base.html')


def lista_clientes_view(request):
    # Jala todos los clientes de PostgreSQL incluyendo su tipo de documento
    clientes = Cliente.objects.select_related('id_tipo_doc').all()
    return render(request, 'clientes_list.html', {'lista_clientes': list(clientes)})

def lista_productos_view(request):
    # Jala todos los productos de PostgreSQL incluyendo su tipo de afectación y unidad de medida
    productos = Producto.objects.select_related('id_tipo_afectacion', 'id_unidad').all()
    return render(request, 'productos_list.html', {'lista_productos': list(productos)})




from django.shortcuts import render
from django.http import JsonResponse
from .models import Cliente, Producto # Asegúrate de que los nombres de los modelos correspondan a tu models.py

def dashboard(request):
    """Controlador del Panel Principal"""
    return render(request, 'base.html')


def lista_clientes_view(request):
    """Controlador para listar Clientes"""
    clientes = Cliente.objects.select_related('id_tipo_doc').all()
    return render(request, 'clientes_list.html', {'lista_clientes': list(clientes)})


def lista_productos_view(request):
    """Controlador para listar Productos"""
    productos = Producto.objects.select_related('id_tipo_afectacion', 'id_unidad').all()
    return render(request, 'productos_list.html', {'lista_productos': list(productos)})






def api_facturas(request):
    """Endpoint oficial para la emisión de Facturas (Código SUNAT 01)"""
    if request.method == 'POST':
        # Aquí procesaremos el JSON enviado por Alpine en el siguiente paso
        return JsonResponse({'success': True})
        
    # Método GET: Carga datos de PostgreSQL y renderiza el formulario
    clientes = Cliente.objects.all().order_by('razon_social')
    productos = Producto.objects.all().order_by('nombre')
    
    context = {
        'titulo': 'Emitir Factura Electrónica',
        'tipo_comprobante_id': '01',
        'clientes': clientes,
        'productos': productos,
    }
    return render(request, 'facturacion/comprobante_form.html', context)


def api_boletas(request):
    """Endpoint oficial para la emisión de Boletas (Código SUNAT 03)"""
    if request.method == 'POST':
        # Aquí procesaremos el JSON enviado por Alpine en el siguiente paso
        return JsonResponse({'success': True})
        
    # Método GET: Carga datos de PostgreSQL y renderiza el formulario
    clientes = Cliente.objects.all().order_by('razon_social')
    productos = Producto.objects.all().order_by('nombre')
    
    context = {
        'titulo': 'Emitir Boleta de Venta',
        'tipo_comprobante_id': '03',
        'clientes': clientes,
        'productos': productos,
    }
    return render(request, 'facturacion/comprobante_form.html', context)