# Facturacion Electronica

## Cargar datos demo

Ejecuta las migraciones antes de cargar la informacion inicial:

```powershell
python manage.py migrate
python manage.py seed_demo
```

El comando crea datos maestros para probar factura, boleta, notas, clientes y productos usando el RUC demo SUNAT `20100066603`.

## Firmar XML

Configura estas variables antes de firmar:

```powershell
SUNAT_CERT_PATH=core/certs/DEMO_Sunat.pfx
SUNAT_CERT_PASSWORD=coloca_password_del_certificado
```

Prueba desde el shell de Django:

```powershell
python manage.py shell
```

```python
from facturacion.models import Comprobante
from facturacion.services.xml_signer import generar_y_firmar_comprobante

c = Comprobante.objects.first()
xml = generar_y_firmar_comprobante(c)
```

## Crear ZIP SUNAT

Prueba desde el shell de Django:

```powershell
python manage.py shell
```

```python
from facturacion.models import Comprobante
from facturacion.services.zip_service import generar_zip_para_comprobante, validar_zip_sunat
from facturacion.services.xml_builder import nombre_archivo_sunat

c = Comprobante.objects.filter(tipo_comprobante="01").first()
zip_bytes = generar_zip_para_comprobante(c)
nombre = nombre_archivo_sunat(c)
print(validar_zip_sunat(zip_bytes, nombre))

b = Comprobante.objects.filter(tipo_comprobante="03").first()
zip_boleta = generar_zip_para_comprobante(b)
nombre_b = nombre_archivo_sunat(b)
print(validar_zip_sunat(zip_boleta, nombre_b))
```

El ZIP debe contener un único XML en la raíz con el mismo nombre SUNAT.
