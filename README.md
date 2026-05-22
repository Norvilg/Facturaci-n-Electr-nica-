# Facturacion Electronica

## Cargar datos demo

Ejecuta las migraciones antes de cargar la informacion inicial:

```powershell
python manage.py migrate
python manage.py seed_demo
```

El comando crea datos maestros para probar factura, boleta, notas, clientes y productos usando el RUC demo SUNAT `20100066603`.
