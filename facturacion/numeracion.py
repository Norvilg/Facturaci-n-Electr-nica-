"""
Numeración correlativa de series — módulo testeable.
"""
from .models import Serie


def siguiente_correlativo(serie: Serie) -> int:
    """
    Obtiene e incrementa el correlativo de la serie (transacción atómica
    debe envolver la llamada desde la vista).
    """
    serie_locked = Serie.objects.select_for_update().get(pk=serie.pk)
    nuevo = serie_locked.correlativo + 1
    serie_locked.correlativo = nuevo
    serie_locked.save(update_fields=['correlativo'])
    return nuevo


def formato_numeracion(serie: str, correlativo: int, padding: int = 8) -> str:
    """Ejemplo: F001-00000012"""
    return f'{serie}-{correlativo:0{padding}d}'


def nombre_archivo_sunat(ruc: str, tipo: str, serie: str, correlativo: int) -> str:
    """Nombre base del XML: RUC-TIPO-SERIE-CORRELATIVO"""
    return f'{ruc}-{tipo}-{serie}-{correlativo:08d}'
