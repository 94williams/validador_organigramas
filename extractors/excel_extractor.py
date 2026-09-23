"""
Extractor de la fuente Excel.

Usa openpyxl (no pandas) porque necesitamos:
- Coordenadas exactas de celda (fila/columna) para trazabilidad.
- Detectar celdas combinadas.
- Iterar hojas y encabezados sin asumir un esquema fijo.

pandas se evita aquí a propósito: openpyxl da control fino de celda a celda,
que es justo lo que pide la trazabilidad (punto 10 del planteamiento).
"""
import os
import re
import sys
from typing import List, Optional, Tuple

import openpyxl
from openpyxl.utils import get_column_letter, column_index_from_string

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from models.models import PuestoRecord, Fuente, Ubicacion, MetodoExtraccion  # noqa: E402
from normalization.normalizer import normalizar_puesto, normalizar_nivel  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger("excel_extractor")


# Rótulos administrativos/de resumen que pueden aparecer en la columna de
# puesto (por ejemplo J) pero no representan puestos reales. Se comparan como
# prefijos después de normalizar para cubrir casos como "INTEGRÓ: Juan Pérez",
# "TOTAL 25" o "TITULAR DEL ÁREA DE ADMINISTRACIÓN: ...".
_EXCEL_PREFIJOS_IGNORADOS = tuple(
    normalizar_puesto(valor)
    for valor in (
        "INTEGRÓ",
        "TITULAR DE UNIDAD ADMINISTRATIVA",
        "TITULAR DEL ÁREA DE ADMINISTRACIÓN",
        "TOTAL",
        "TOTAL ACTUAL",
        "TOTAL PROPUESTO",
        "VARIACIÓN EN COSTO",
        "NO. PLAZAS ACTUAL",
        "NO. PLAZAS PROPUESTA",
        "VARIACIÓN EN PLAZAS",
    )
)


def _es_fila_ignorada_excel(valor) -> bool:
    """True cuando la celda comienza con un rótulo administrativo/resumen."""
    if valor is None:
        return False

    normalizado = normalizar_puesto(str(valor))
    if not normalizado:
        return False

    return any(normalizado.startswith(prefijo) for prefijo in _EXCEL_PREFIJOS_IGNORADOS)


def _texto_encabezado_coincide(valor, candidatos: List[str]) -> bool:
    if valor is None:
        return False
    v = normalizar_puesto(str(valor))
    # Permite coincidencias con encabezados que incluyen variantes reales del
    # texto ("denominacion del puesto", "denominacion", "nivel orgánico")
    # o espacios/puntuación extra.
    return any(c in v for c in candidatos) or any(v == c or v.startswith(c) or v.endswith(c) for c in candidatos)


def _buscar_columnas_por_encabezado(ws) -> Optional[Tuple[int, int, int]]:
    """
    Busca en las primeras N filas una fila que contenga encabezados
    reconocibles de puesto y nivel. Regresa (fila_header, col_puesto, col_nivel)
    o None si no se encuentra.
    """
    max_filas = min(config.EXCEL_MAX_FILAS_BUSQUEDA_HEADER, ws.max_row)
    for fila_idx in range(1, max_filas + 1):
        col_puesto, col_nivel = None, None
        for cell in ws[fila_idx]:
            # Se evalúa primero "nivel" porque encabezados como "Nivel del
            # puesto" contienen la palabra "puesto" y podrían confundirse
            # con la columna de nombre de puesto si se evaluara al revés.
            if _texto_encabezado_coincide(cell.value, config.EXCEL_HEADERS_NIVEL):
                col_nivel = cell.column
            elif _texto_encabezado_coincide(cell.value, config.EXCEL_HEADERS_PUESTO):
                col_puesto = cell.column
        if col_puesto and col_nivel:
            return fila_idx, col_puesto, col_nivel
    return None


def extraer_excel(ruta_archivo: str, hoja: Optional[str] = None) -> List[PuestoRecord]:
    """
    Extrae registros de puesto/nivel de un archivo Excel.

    Estrategia:
    1. Intentar localizar encabezados reconocibles (nombre flexible) en
       cualquiera de las hojas (o solo en `hoja` si se especifica).
    2. Si no se encuentran encabezados, usar el fallback de columnas fijas
       (config.EXCEL_FALLBACK_COL_PUESTO / _NIVEL), asumiendo fila 1 = header.
    3. Ignorar filas vacías y rótulos administrativos/de resumen.
    4. Registrar celdas combinadas como advertencia (no error fatal).
    """
    registros: List[PuestoRecord] = []
    nombre_archivo = os.path.basename(ruta_archivo)

    try:
        wb = openpyxl.load_workbook(ruta_archivo, data_only=True)
    except Exception as e:
        logger.error(f"No se pudo abrir el Excel '{ruta_archivo}': {e}")
        registros.append(PuestoRecord(
            fuente=Fuente.EXCEL, puesto_original="", nivel_original=None,
            ubicacion=Ubicacion(archivo=nombre_archivo),
            error=f"Archivo Excel no legible o corrupto: {e}",
        ))
        return registros

    hojas = [hoja] if hoja else wb.sheetnames

    for nombre_hoja in hojas:
        if nombre_hoja not in wb.sheetnames:
            logger.warning(f"Hoja '{nombre_hoja}' no existe en el archivo, se omite.")
            continue
        ws = wb[nombre_hoja]

        # celdas combinadas -> log informativo (no rompe la extracción,
        # openpyxl regresa el valor solo en la celda superior-izquierda)
        if ws.merged_cells.ranges:
            logger.info(
                f"Hoja '{nombre_hoja}': {len(ws.merged_cells.ranges)} rango(s) de celdas combinadas detectado(s)."
            )

        header_info = _buscar_columnas_por_encabezado(ws)
        if header_info:
            fila_header, col_puesto_idx, col_nivel_idx = header_info
            fila_inicio = fila_header + 1
            logger.info(
                f"Hoja '{nombre_hoja}': encabezados detectados en fila {fila_header} "
                f"(puesto={get_column_letter(col_puesto_idx)}, nivel={get_column_letter(col_nivel_idx)})"
            )
        else:
            col_puesto_idx = column_index_from_string(config.EXCEL_FALLBACK_COL_PUESTO)
            col_nivel_idx = column_index_from_string(config.EXCEL_FALLBACK_COL_NIVEL)
            fila_inicio = 2  # se asume fila 1 = header aunque no se haya reconocido
            logger.warning(
                f"Hoja '{nombre_hoja}': no se reconocieron encabezados; "
                f"usando columnas fijas de respaldo "
                f"({config.EXCEL_FALLBACK_COL_PUESTO}/{config.EXCEL_FALLBACK_COL_NIVEL})."
            )

        col_puesto_letra = get_column_letter(col_puesto_idx)
        col_nivel_letra = get_column_letter(col_nivel_idx)

        for fila_idx in range(fila_inicio, ws.max_row + 1):
            val_puesto = ws.cell(row=fila_idx, column=col_puesto_idx).value
            val_nivel = ws.cell(row=fila_idx, column=col_nivel_idx).value

            if val_puesto is None or not str(val_puesto).strip():
                continue  # fila vacía en la columna clave, se ignora silenciosamente

            if _es_fila_ignorada_excel(val_puesto):
                logger.debug(
                    f"Hoja '{nombre_hoja}', fila {fila_idx}: rótulo administrativo/resumen ignorado: {val_puesto!r}"
                )
                continue

            puesto_str = str(val_puesto).strip()
            nivel_str = None if val_nivel is None else val_nivel

            ubicacion = Ubicacion(
                archivo=nombre_archivo, hoja=nombre_hoja, fila=fila_idx,
                columna=f"{col_puesto_letra}/{col_nivel_letra}",
            )

            registros.append(PuestoRecord(
                fuente=Fuente.EXCEL,
                puesto_original=puesto_str,
                nivel_original=None if nivel_str is None else str(nivel_str),
                puesto_normalizado=normalizar_puesto(puesto_str),
                nivel_normalizado=normalizar_nivel(nivel_str) if nivel_str is not None else None,
                ubicacion=ubicacion,
                metodo_extraccion=MetodoExtraccion.CELDA_EXCEL,
                confianza_extraccion=1.0,
            ))

    logger.info(f"Excel '{nombre_archivo}': {len(registros)} registro(s) extraído(s).")
    return registros
