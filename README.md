# Sistema de Facturación Electrónica (SUNAT — UBL 2.1)

Aplicación web en **Django** para emitir facturas, boletas, notas de crédito/débito y guías de remisión, con integración al ciclo de envío SUNAT (XML firmado + CDR).

## Requisitos

- Python 3.11+
- Docker (PostgreSQL + pgAdmin opcional)
- Git

## Instalación y puesta en marcha

### 1. Clonar e instalar dependencias

```bash
git clone https://github.com/romeromyr/facturacion-electronica-2026.git
cd facturacion-electronica-2026
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. Base de datos (Docker)

```bash
docker compose up -d
```

| Servicio | URL / Puerto |
|----------|----------------|
| PostgreSQL | `localhost:5433` — BD: `db_facturacion`, user: `postgres`, pass: `sunat_secure_pass` |
| pgAdmin | http://localhost:5050 — `admin@admin.com` / `admin123` |

### 3. Migraciones, roles y usuarios de prueba

```bash
python manage.py migrate
python manage.py setup_roles
python manage.py setup_usuarios
```

| Usuario | Contraseña | Rol |
|---------|------------|-----|
| `administrador` | `Admin2026!` | Administrador |
| `contador` | `Contador2026!` | Contador |
| `emisor` | `Emisor2026!` | Emisor |

(Opcional: `python manage.py createsuperuser` para otro admin.)

### 4. SUNAT (conexión real beta)

Por defecto cada comprobante se envía a **SUNAT beta** vía SOAP (`SUNAT_URL_BETA`).

**Requisito:** certificado `.pfx` en `core/certs/DEMO_Sunat.pfx` (ver `core/certs/README.txt`).

**Importante:** el RUC del emisor en la base de datos debe coincidir con el RUC del certificado.  
El certificado demo incluido corresponde a **20100066603** (no a 20100070970). Si el emisor en BD usa otro RUC, SUNAT rechazará el comprobante.

Credenciales del emisor en la BD (`usuario_sol`, `clave_sol`) o en `core/settings.py`.  
En beta de prueba SUNAT: usuario `MODDATOS`, clave `MODDATOS` (usuario SOAP = `{RUC}MODDATOS`).

Dependencias de firma: `xfep-sign`, `xmlsec` (ver `requirements.txt`).

Si SUNAT responde con un código de error, revise `storage/xmls/logs/ultima_respuesta_*.xml`.

El envío lee el XML de `storage/xmls/firmados/`, crea el `.zip`, llama a  
`https://e-beta.sunat.gob.pe/ol-ti-itcpfegem-beta/billService` y guarda el CDR en `storage/xmls/cdrs/`.

Solo para tests locales sin red: `$env:SUNAT_MODO = "simulado"`

### 5. Ejecutar servidor

```bash
python manage.py runserver
```

Aplicación: **http://127.0.0.1:8000/**  
Login: **http://127.0.0.1:8000/login/**

## Enlaces principales

| Módulo | URL |
|--------|-----|
| Dashboard | http://127.0.0.1:8000/ |
| Facturas | http://127.0.0.1:8000/api/facturas/ |
| Boletas | http://127.0.0.1:8000/api/boletas/ |
| Notas crédito / débito | `/api/notas-credito/`, `/api/notas-debito/` |
| Imprimir comprobantes | http://127.0.0.1:8000/comprobantes/ |
| **Swagger API** | http://127.0.0.1:8000/api/docs/ |
| Esquema OpenAPI | http://127.0.0.1:8000/api/schema/ |

## Documentación XML

Ver [docs/ESTRUCTURA_XML.md](docs/ESTRUCTURA_XML.md) — namespaces UBL, cabecera, líneas, totales, CDR y rutas de `storage/xmls/`.

## Tests (rúbrica académica)

Cubre **cálculo tributario (IGV)**, **numeración correlativa** y **ciclo SUNAT** (XML + CDR simulado).

```bash
# Ejecutar tests (usa SQLite automáticamente)
python manage.py test facturacion.tests

# Cobertura sobre módulos evaluados
pip install coverage
coverage run --source=facturacion/calculos_tributarios,facturacion/numeracion,facturacion/generarXmlFirmar,facturacion/services_sunat_conexion manage.py test facturacion.tests
coverage report -m
```

Módulos bajo prueba:

- `facturacion/calculos_tributarios.py` — IGV 18%, totales, notas de crédito
- `facturacion/numeracion.py` — correlativo de series
- `facturacion/generarXmlFirmar.py` — generación UBL
- `facturacion/services_sunat_conexion.py` — respuesta CDR

## Estructura del proyecto

```
core/                 # settings, urls
facturacion/
  models.py           # Cliente, Producto, Comprobante, Detalle...
  views.py            # Emisión y dashboard
  calculos_tributarios.py
  numeracion.py
  generarXmlFirmar.py   # XML UBL + envío
  services_sunat.py     # Adaptador SUNAT
  tests/              # Tests unitarios
templates/            # AdminLTE + formularios
storage/xmls/         # XML firmados y CDR
static/               # CSS, imágenes
docs/ESTRUCTURA_XML.md
```

## API REST (emisión)

POST JSON a `/api/facturas/` o `/api/boletas/`:

```json
{
  "cliente_id": 1,
  "forma_pago": "Contado",
  "tipo_comprobante": "03",
  "totales": { "op_grabadas": "10.00", "igv": "1.80", "total": "11.80" },
  "items": [{ "id": 1, "cantidad": 1, "v_unitario": "10.00" }],
  "cuotas": []
}
```

Documentación interactiva: **http://127.0.0.1:8000/api/docs/**

## Repositorio en GitHub

| Recurso | Enlace |
|---------|--------|
| Repositorio | https://github.com/romeromyr/facturacion-electronica-2026 |
| Clonar (HTTPS) | `git clone https://github.com/romeromyr/facturacion-electronica-2026.git` |

### Subir cambios (mantenedor)

```bash
git add .
git commit -m "Descripción del cambio"
git push origin main
```

## Licencia / curso

Proyecto académico — Facturación Electrónica 2026-I.
