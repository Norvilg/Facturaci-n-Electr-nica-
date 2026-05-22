"""
services_sunat.py  —  ADAPTADOR
================================
Archivo a colocar en: SISTEMAFACTURACION/facturacion/services_sunat.py

Puente entre:
  - TU frontend  : JSON enviado por Alpine.js desde comprobante_form.html
  - TU BD        : modelos en facturacion/models.py  (Comprobante, Detalle, etc.)
  - MOTOR SUNAT  : services.py de tu compañero (genera XML, firma, envía a SUNAT)

INSTRUCCIONES DE USO
--------------------
1. Copia este archivo en SISTEMAFACTURACION/facturacion/services_sunat.py
2. Copia el services.py de tu compañero en SISTEMAFACTURACION/facturacion/services_compañero.py
3. Asegúrate de que las rutas de settings (SUNAT_CERT_PATH, etc.) estén en tu settings.py
4. Llama a procesar_comprobante_completo(comprobante, detalles) desde tu views.py
"""

import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from dataclasses import dataclass, field
from typing import List

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# OBJETOS PROXY
# Simulan los modelos del compañero a partir de tus modelos propios.
# El services.py del compañero espera objetos con ciertos atributos:
#   comprobante.empresa.ruc, comprobante.empresa.razon_social, etc.
#   comprobante.cliente.numero_documento, comprobante.cliente.tipo_documento, etc.
#   comprobante.detalles  → iterable con objetos DetalleProxy
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EmpresaProxy:
    """
    Mapea tu modelo Emisor → estructura que espera services.py del compañero.
    
    Tu modelo Emisor tiene:
      ruc, razon_social, direccion, usuario_sol, clave_sol
    """
    ruc: str
    razon_social: str
    direccion: str
    usuario_sol: str = ''
    clave_sol: str = ''


@dataclass
class SerieProxy:
    """
    Mapea tu modelo Serie → estructura que espera services.py del compañero.
    
    Tu modelo Serie tiene:
      serie (ej: 'F001'), correlativo
    """
    serie: str


@dataclass
class ClienteProxy:
    """
    Mapea tu modelo Cliente → estructura que espera services.py del compañero.

    TU modelo Cliente:           COMPAÑERO espera:
      nrodoc                  →  numero_documento
      id_tipo_doc.descripcion →  tipo_documento  (debe ser '6' para RUC, '1' para DNI)
      razon_social            →  razon_social
      direccion               →  direccion
    """
    numero_documento: str
    tipo_documento: str      # '6' = RUC, '1' = DNI, '0' = Sin doc
    razon_social: str
    direccion: str


@dataclass
class ProductoProxy:
    """
    Mapea tu modelo Producto → estructura que espera services.py del compañero.

    TU modelo Producto:          COMPAÑERO espera:
      nombre                  →  descripcion
      id_unidad.descripcion   →  unidad_medida  (ej: 'NIU', 'ZZ')
      id_tipo_afectacion.codigo → tipo_afectacion_igv
    """
    descripcion: str
    unidad_medida: str
    tipo_afectacion_igv: str  # '10' = gravado, '20' = exonerado, '30' = inafecto

    def tiene_igv(self) -> bool:
        """Devuelve True si el producto está gravado con IGV."""
        return self.tipo_afectacion_igv in ('10', '11', '12', '13', '14', '15', '16', '17')


@dataclass
class DetalleProxy:
    """
    Mapea tu modelo Detalle → estructura que espera services.py del compañero.

    TU modelo Detalle:           COMPAÑERO espera:
      cantidad                →  cantidad
      valor_unitario          →  precio_unitario  (precio SIN IGV)
      igv                     →  igv_linea
      valor_total             →  subtotal         (base sin IGV)
      importe_total           →  total            (con IGV)
      id_producto.nombre      →  descripcion
      id_producto.id_unidad   →  unidad_medida
    """
    producto: ProductoProxy
    descripcion: str
    cantidad: Decimal
    unidad_medida: str
    precio_unitario: Decimal   # sin IGV
    descuento: Decimal
    igv_linea: Decimal
    subtotal: Decimal          # base sin IGV
    total: Decimal             # con IGV


@dataclass
class ComprobanteProxy:
    """
    Objeto completo que espera services.py del compañero.

    Atributos requeridos por _generar_xml():
      empresa         → EmpresaProxy
      serie           → SerieProxy
      cliente         → ClienteProxy
      tipo            → '01' (factura) o '03' (boleta)
      numero          → int correlativo
      fecha_emision   → date
      moneda          → 'PEN'
      total           → Decimal
      subtotal        → Decimal
      igv             → Decimal
      detalles        → manager-like con .select_related().all()
      
    Atributos requeridos por nombre_archivo_sunat():
      empresa.ruc, tipo, serie.serie, numero
      
    Atributos que services.py escribe (necesitas pasarlos vacíos):
      xml_firmado, sunat_ticket, sunat_cdr, sunat_descripcion, estado, id
    """
    empresa: EmpresaProxy
    serie: SerieProxy
    cliente: ClienteProxy
    tipo: str
    numero: int
    fecha_emision: date
    moneda: str
    total: Decimal
    subtotal: Decimal
    igv: Decimal
    _detalles: List[DetalleProxy]

    # Campos que services.py escribe — inicializan vacíos
    xml_firmado: str = ''
    sunat_ticket: str = ''
    sunat_cdr: str = ''
    sunat_descripcion: str = ''
    estado: str = 'BORRADOR'
    id: int = 0

    def nombre_archivo_sunat(self) -> str:
        """Replica el método del modelo del compañero."""
        return f"{self.empresa.ruc}-{self.tipo}-{self.serie.serie}-{self.numero:08d}"

    def es_factura(self) -> bool:
        return self.tipo == '01'

    def es_boleta(self) -> bool:
        return self.tipo == '03'

    def save(self, update_fields=None):
        """
        El services.py del compañero llama comprobante.save() para persistir
        xml_firmado, estado, sunat_ticket, etc.
        Aquí simplemente ignoramos esa llamada porque nosotros persistimos
        en NUESTRA BD (modelo Comprobante de facturacion/models.py).
        Los valores ya quedarán en los atributos del proxy para que los leas
        después de llamar a enviar_a_sunat().
        """
        pass

    @property
    def detalles(self):
        """Devuelve un objeto que simula el manager de Django."""
        return _DetallesManager(self._detalles)


class _DetallesManager:
    """Simula el RelatedManager de Django para que services.py pueda hacer
    comprobante.detalles.select_related('producto').all()"""
    def __init__(self, lista):
        self._lista = lista

    def select_related(self, *args):
        return self

    def all(self):
        return self._lista


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL DEL ADAPTADOR
# ─────────────────────────────────────────────────────────────────────────────

def procesar_comprobante_completo(tu_comprobante, tus_detalles) -> dict:
    """
    Punto de entrada del adaptador. Recibe tus objetos de BD y devuelve
    el resultado de SUNAT.

    Parámetros
    ----------
    tu_comprobante : facturacion.models.Comprobante
        El comprobante ya guardado en TU BD.
    tus_detalles : list[facturacion.models.Detalle]
        Los detalles ya guardados en TU BD.

    Retorna
    -------
    dict con claves: estado, codigo, descripcion, ticket, xml_firmado
    """
    try:
        proxy = _construir_proxy(tu_comprobante, tus_detalles)
        
        # Importamos el services.py del compañero
        # (debe estar copiado como services_companero.py en tu app)
        from . import generarXmlFirmar as svc

        resultado = svc.enviar_a_sunat(proxy)

        # Actualizamos TU BD con la respuesta de SUNAT
        _actualizar_tu_comprobante(tu_comprobante, proxy, resultado)

        return resultado

    except Exception as e:
        logger.error(f"Error en adaptador SUNAT: {e}", exc_info=True)
        return {
            'estado': 'RECHAZADO',
            'codigo': '9999',
            'descripcion': f'Error interno del adaptador: {str(e)}',
            'ticket': '',
        }


def solo_generar_xml(tu_comprobante, tus_detalles) -> bytes:
    """
    Genera y firma el XML sin enviarlo a SUNAT.
    Útil para previsualización o debug.
    """
    proxy = _construir_proxy(tu_comprobante, tus_detalles)
    from . import services_companero as svc
    return svc.generar_xml_y_firmar(proxy)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTRUCCIÓN DEL PROXY
# ─────────────────────────────────────────────────────────────────────────────

def _construir_proxy(tu_comprobante, tus_detalles) -> ComprobanteProxy:
    """
    Mapea TUS modelos → objetos Proxy que espera el services.py del compañero.
    """

    # ── 1. Empresa (tu modelo Emisor) ─────────────────────────────────────────
    emisor = tu_comprobante.id_emisor
    empresa_proxy = EmpresaProxy(
        ruc          = emisor.ruc,
        razon_social = emisor.razon_social,
        direccion    = emisor.direccion or 'SIN DIRECCION',
        usuario_sol  = emisor.usuario_sol,
        clave_sol    = emisor.clave_sol,
    )

    # ── 2. Serie ──────────────────────────────────────────────────────────────
    serie_proxy = SerieProxy(
        serie = tu_comprobante.serie,   # campo CharField 'F001' / 'B001'
    )

    # ── 3. Cliente ────────────────────────────────────────────────────────────
    cliente = tu_comprobante.id_cliente
    
    # Tu tipo_doc es FK a TipoDocumento. El compañero espera '6' (RUC) o '1' (DNI).
    # Mapeamos por descripción o por id según tu tabla tipo_documento.
    tipo_doc_codigo = _mapear_tipo_documento(cliente.id_tipo_doc)

    cliente_proxy = ClienteProxy(
        numero_documento = cliente.nrodoc,
        tipo_documento   = tipo_doc_codigo,
        razon_social     = cliente.razon_social,
        direccion        = cliente.direccion or '',
    )

    # ── 4. Detalles ───────────────────────────────────────────────────────────
    detalles_proxy = []
    for det in tus_detalles:
        producto = det.id_producto

        # Tipo afectación: tu tabla tiene campo 'codigo' (ej: '10', '20', '30')
        from .catalogos_sunat import codigo_afectacion_igv

        raw_afectacion = (
            producto.id_tipo_afectacion.codigo if producto.id_tipo_afectacion else '10'
        )
        tipo_afectacion = codigo_afectacion_igv(raw_afectacion)

        # Unidad de medida: tu tabla Unidad tiene campo 'descripcion'
        # El compañero espera el código SUNAT (ej: 'NIU', 'ZZ')
        # Si tu campo descripcion ya es el código SUNAT, úsalo directamente.
        # Si es texto largo, mapea con _mapear_unidad_medida().
        unidad = _mapear_unidad_medida(producto.id_unidad.descripcion if producto.id_unidad else 'NIU')

        producto_proxy = ProductoProxy(
            descripcion         = producto.nombre,
            unidad_medida       = unidad,
            tipo_afectacion_igv = tipo_afectacion,
        )

        detalle_proxy = DetalleProxy(
            producto        = producto_proxy,
            descripcion     = producto.nombre,
            cantidad        = Decimal(str(det.cantidad)),
            unidad_medida   = unidad,
            precio_unitario = Decimal(str(det.valor_unitario)),   # sin IGV
            descuento       = Decimal('0.00'),
            igv_linea       = Decimal(str(det.igv)),
            subtotal        = Decimal(str(det.valor_total)),       # base sin IGV
            total           = Decimal(str(det.importe_total)),     # con IGV
        )
        detalles_proxy.append(detalle_proxy)

    # ── 5. Tipo de comprobante ────────────────────────────────────────────────
    # Tu modelo guarda el tipo como FK a TipoComprobante.
    # Necesitamos '01' para factura, '03' para boleta.
    tipo_codigo = _mapear_tipo_comprobante(tu_comprobante)

    # ── 6. Moneda ─────────────────────────────────────────────────────────────
    # Tu modelo tiene FK a Moneda. El compañero espera 'PEN' o 'USD'.
    moneda_codigo = _mapear_moneda(tu_comprobante.id_moneda)

    # ── 7. Armar proxy completo ───────────────────────────────────────────────
    proxy = ComprobanteProxy(
        empresa       = empresa_proxy,
        serie         = serie_proxy,
        cliente       = cliente_proxy,
        tipo          = tipo_codigo,
        numero        = tu_comprobante.correlativo,
        fecha_emision = tu_comprobante.fecha_emision,
        moneda        = moneda_codigo,
        subtotal      = Decimal(str(tu_comprobante.op_grabadas)),
        igv           = Decimal(str(tu_comprobante.igv)),
        total         = Decimal(str(tu_comprobante.total)),
        _detalles     = detalles_proxy,
        id            = tu_comprobante.id_comprobante,
    )

    return proxy


# ─────────────────────────────────────────────────────────────────────────────
# ACTUALIZAR TU BD CON RESPUESTA SUNAT
# ─────────────────────────────────────────────────────────────────────────────

def _actualizar_tu_comprobante(tu_comprobante, proxy: ComprobanteProxy, resultado: dict):
    """
    Escribe en TU modelo Comprobante los datos que devolvió SUNAT.
    
    Tu modelo tiene: xmlbase64, cdrbase64, codigo_sunat, mensaje_sunat,
                     estado_comprobante, hash, nombrexml
    """
    try:
        # XML firmado — el services.py del compañero lo guardó en proxy.xml_firmado
        # que es el nombre del archivo. Leemos el contenido si lo necesitas en base64.
        if proxy.xml_firmado:
            tu_comprobante.nombrexml = proxy.xml_firmado

        # Respuesta SUNAT
        tu_comprobante.codigo_sunat  = resultado.get('codigo', '')
        tu_comprobante.mensaje_sunat = resultado.get('descripcion', '')[:100]

        # Estado: '1' = aceptado, '2' = rechazado (ajusta según tu lógica)
        tu_comprobante.estado_comprobante = (
            '1' if resultado.get('estado') == 'ACEPTADO' else '2'
        )

        tu_comprobante.save()

    except Exception as e:
        logger.error(f"Error actualizando comprobante en BD local: {e}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# FUNCIONES DE MAPEO
# Ajusta estos mapeos según los valores exactos de TUS tablas de BD.
# ─────────────────────────────────────────────────────────────────────────────

def _mapear_tipo_documento(tipo_doc_obj) -> str:
    """
    Tu tabla tipo_documento tiene: id_tipo_doc, descripcion
    Mapea a los códigos SUNAT: '6' = RUC, '1' = DNI, '4' = CE, '0' = Sin doc
    
    AJUSTA el diccionario según los valores exactos de tu tabla.
    """
    if tipo_doc_obj is None:
        return '1'

    # Mapeo por descripción (ajusta según tu BD)
    desc = tipo_doc_obj.descripcion.upper().strip()
    mapeo = {
        'RUC'                : '6',
        'DNI'                : '1',
        'CARNET DE EXTRANJERIA': '4',
        'CE'                 : '4',
        'PASAPORTE'          : '7',
        'SIN DOCUMENTO'      : '0',
        '-'                  : '0',
    }
    return mapeo.get(desc, '1')  # default DNI si no encuentra


def _mapear_tipo_comprobante(tu_comprobante) -> str:
    """
    Tu modelo Comprobante tiene id_tipo_comprobante FK a TipoComprobante.
    TipoComprobante tiene: id_tipo_comprobante (int), descripcion.
    
    También tienes el campo serie ('F001' o 'B001') que es más confiable.
    Mapeamos por serie primero.
    """
    serie = tu_comprobante.serie or ''
    if serie.startswith('F'):
        return '01'
    if serie.startswith('B'):
        return '03'

    # Fallback por descripción del tipo
    if tu_comprobante.id_tipo_comprobante:
        desc = (tu_comprobante.id_tipo_comprobante.descripcion or '').upper()
        if 'FACTURA' in desc:
            return '01'
        if 'BOLETA' in desc:
            return '03'

    return '01'  # default factura


def _mapear_moneda(moneda_obj) -> str:
    """
    Tu tabla moneda tiene: id_moneda, descripcion
    Mapea a códigos ISO: 'PEN', 'USD'
    """
    if moneda_obj is None:
        return 'PEN'

    desc = moneda_obj.descripcion.upper().strip()
    mapeo = {
        'SOLES'              : 'PEN',
        'SOL'                : 'PEN',
        'PEN'                : 'PEN',
        'DÓLARES'            : 'USD',
        'DOLARES'            : 'USD',
        'DÓLAR'              : 'USD',
        'DOLAR'              : 'USD',
        'USD'                : 'USD',
    }
    return mapeo.get(desc, 'PEN')


def _mapear_unidad_medida(descripcion: str) -> str:
    """
    Tu tabla Unidad tiene descripcion en texto.
    El compañero espera el código SUNAT (catálogo 6 SUNAT).
    
    Si tu tabla ya guarda el código directamente (ej: 'NIU'), retorna tal cual.
    Si guarda texto largo, mapea aquí.
    
    AJUSTA según los valores reales de tu tabla.
    """
    if not descripcion:
        return 'NIU'

    desc = descripcion.upper().strip()

    # Si ya es un código corto SUNAT (2-3 letras), úsalo directo
    if len(desc) <= 3:
        return desc

    mapeo = {
        'UNIDAD'             : 'NIU',
        'UNIDADES'           : 'NIU',
        'SERVICIO'           : 'ZZ',
        'SERVICIOS'          : 'ZZ',
        'KILOGRAMO'          : 'KGM',
        'KILOGRAMOS'         : 'KGM',
        'LITRO'              : 'LTR',
        'LITROS'             : 'LTR',
        'METRO'              : 'MTR',
        'METROS'             : 'MTR',
        'CAJA'               : 'BX',
        'CAJAS'              : 'BX',
        'DOCENA'             : 'DZN',
        'DOCENAS'            : 'DZN',
    }
    return mapeo.get(desc, 'NIU')  # default NIU (unidad)