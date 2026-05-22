"""
Roles y permisos del sistema de facturación (3 roles).

Comando: python manage.py setup_usuarios
"""

APP_LABEL = 'facturacion'

PERM_DASHBOARD = 'acceso_dashboard'
PERM_EMIT_FACTURA = 'emit_factura'
PERM_EMIT_BOLETA = 'emit_boleta'
PERM_EMIT_NC = 'emit_nota_credito'
PERM_EMIT_ND = 'emit_nota_debito'
PERM_EMIT_GUIA = 'emit_guia_remision'
PERM_CONSULTAR = 'consultar_comprobantes'
PERM_BUSCAR = 'buscar_comprobante'
PERM_CLIENTES = 'gestionar_clientes'
PERM_CRUD_CLIENTES = 'crud_clientes'
PERM_PRODUCTOS = 'gestionar_productos'
PERM_CRUD_PRODUCTOS = 'crud_productos'
PERM_LIBRO_VENTAS = 'libro_ventas'
PERM_VER_PERFIL = 'ver_perfil_emisor'
PERM_CONFIG_EMISOR = 'configurar_emisor'
PERM_SUNAT = 'procesos_sunat'

ALL_CUSTOM_PERMS = (
    PERM_DASHBOARD,
    PERM_EMIT_FACTURA,
    PERM_EMIT_BOLETA,
    PERM_EMIT_NC,
    PERM_EMIT_ND,
    PERM_EMIT_GUIA,
    PERM_CONSULTAR,
    PERM_BUSCAR,
    PERM_CLIENTES,
    PERM_CRUD_CLIENTES,
    PERM_PRODUCTOS,
    PERM_CRUD_PRODUCTOS,
    PERM_LIBRO_VENTAS,
    PERM_VER_PERFIL,
    PERM_CONFIG_EMISOR,
    PERM_SUNAT,
)

PERMISO_POR_TIPO_SUNAT = {
    '01': PERM_EMIT_FACTURA,
    '03': PERM_EMIT_BOLETA,
    '07': PERM_EMIT_NC,
    '08': PERM_EMIT_ND,
    '09': PERM_EMIT_GUIA,
}

ROLES = {
    'Administrador': list(ALL_CUSTOM_PERMS),
    'Contador': [
        PERM_DASHBOARD,
        PERM_CONSULTAR,
        PERM_BUSCAR,
        PERM_CLIENTES,
        PERM_PRODUCTOS,
        PERM_LIBRO_VENTAS,
        PERM_VER_PERFIL,
        PERM_CONFIG_EMISOR,
        PERM_SUNAT,
    ],
    'Emisor': [
        PERM_DASHBOARD,
        PERM_EMIT_FACTURA,
        PERM_EMIT_BOLETA,
        PERM_EMIT_NC,
        PERM_EMIT_ND,
        PERM_EMIT_GUIA,
        PERM_CONSULTAR,
        PERM_BUSCAR,
        PERM_CLIENTES,
        PERM_PRODUCTOS,
    ],
}

RUTAS_POST_LOGIN = (
    (PERM_DASHBOARD, 'dashboard'),
    (PERM_EMIT_FACTURA, 'api_facturas'),
    (PERM_LIBRO_VENTAS, 'libro_ventas'),
    (PERM_CONSULTAR, 'lista_comprobantes'),
    (PERM_CLIENTES, 'lista_clientes'),
    (PERM_PRODUCTOS, 'lista_productos'),
    (PERM_VER_PERFIL, 'perfil_emisor'),
)

USUARIOS_SISTEMA = (
    {
        'username': 'administrador',
        'password': 'Admin2026!',
        'rol': 'Administrador',
        'email': 'administrador@facturacion.local',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'contador',
        'password': 'Contador2026!',
        'rol': 'Contador',
        'email': 'contador@facturacion.local',
        'is_staff': False,
        'is_superuser': False,
    },
    {
        'username': 'emisor',
        'password': 'Emisor2026!',
        'rol': 'Emisor',
        'email': 'emisor@facturacion.local',
        'is_staff': False,
        'is_superuser': False,
    },
)

ROLES_OBSOLETOS = (
    'Facturador',
    'Cajero',
    'Catalogos',
    'Consultor',
    'Configurador',
)
