"""
Vistas documentadas para Swagger (OpenAPI 3) — rúbrica docente.
"""
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from rest_framework import serializers
from rest_framework.decorators import api_view
from rest_framework.response import Response


class TotalesSerializer(serializers.Serializer):
    op_grabadas = serializers.DecimalField(max_digits=11, decimal_places=2)
    igv = serializers.DecimalField(max_digits=11, decimal_places=2)
    total = serializers.DecimalField(max_digits=11, decimal_places=2)


class ItemEmisionSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text='id_producto en PostgreSQL')
    cantidad = serializers.DecimalField(max_digits=15, decimal_places=6)
    v_unitario = serializers.DecimalField(max_digits=15, decimal_places=6, help_text='Precio sin IGV')


class EmisionComprobanteSerializer(serializers.Serializer):
    cliente_id = serializers.IntegerField()
    forma_pago = serializers.ChoiceField(choices=['Contado', 'Credito'])
    tipo_comprobante = serializers.ChoiceField(choices=['01', '03'], help_text='01 Factura, 03 Boleta')
    totales = TotalesSerializer()
    items = ItemEmisionSerializer(many=True)
    cuotas = serializers.ListField(child=serializers.DictField(), required=False)


class BuscarComprobanteResponseSerializer(serializers.Serializer):
    encontrado = serializers.BooleanField()
    id = serializers.IntegerField(required=False)
    numeracion = serializers.CharField(required=False)
    cliente_id = serializers.IntegerField(required=False)
    total = serializers.CharField(required=False)
    estado = serializers.CharField(required=False, help_text='1=Aceptado')


@extend_schema(
    tags=['Comprobantes'],
    summary='Emitir factura electrónica (01)',
    description='POST JSON desde el formulario Alpine.js. Guarda en BD y envía a SUNAT.',
    request=EmisionComprobanteSerializer,
    responses={200: OpenApiExample('Éxito', value={'success': True, 'numeracion': 'F001-00000001'})},
)
@api_view(['GET', 'POST'])
def doc_api_facturas(request):
    """Documentación del endpoint real: `/api/facturas/`."""
    return Response({
        'endpoint': '/api/facturas/',
        'metodo': 'POST',
        'tipo_sunat': '01',
        'nota': 'Use POST con JSON para emitir. GET muestra el formulario web.',
    })


@extend_schema(
    tags=['Comprobantes'],
    summary='Emitir boleta de venta (03)',
    request=EmisionComprobanteSerializer,
)
@api_view(['GET', 'POST'])
def doc_api_boletas(request):
    return Response({
        'endpoint': '/api/boletas/',
        'metodo': 'POST',
        'tipo_sunat': '03',
    })


@extend_schema(
    tags=['Comprobantes'],
    summary='Buscar comprobante aceptado',
    parameters=[
        OpenApiParameter('serie', str, description='Ej. F001'),
        OpenApiParameter('numero', int, description='Correlativo'),
    ],
    responses={200: BuscarComprobanteResponseSerializer},
)
@api_view(['GET'])
def doc_buscar_comprobante(request):
    return Response({
        'endpoint': '/api/comprobantes/buscar/',
        'ejemplo': '/api/comprobantes/buscar/?serie=F001&numero=52',
    })


@extend_schema(
    tags=['Comprobantes'],
    summary='Emitir nota de crédito (07)',
)
@api_view(['GET', 'POST'])
def doc_api_notas_credito(request):
    return Response({'endpoint': '/api/notas-credito/', 'tipo_sunat': '07'})


@extend_schema(
    tags=['Comprobantes'],
    summary='Emitir nota de débito (08)',
)
@api_view(['GET', 'POST'])
def doc_api_notas_debito(request):
    return Response({'endpoint': '/api/notas-debito/', 'tipo_sunat': '08'})
