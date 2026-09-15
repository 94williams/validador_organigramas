"""
Extractor del documento Word (tablas de puesto/nivel).

Se soportan dos modos de entrada:
- .docx nativo (preferido): usa python-docx, más confiable porque las
  celdas de tabla están perfectamente delimitadas en el XML — la
  extracción NO depende de que la tabla tenga bordes visibles.
- PDF convertido desde Word (fallback): usa pdfplumber en dos niveles:
  1) detección de tabla por líneas (rápida y precisa cuando la tabla
     tiene bordes visibles);
  2) si una página no arroja ninguna tabla utilizable (caso real y común:
     tablas SIN bordes visibles, donde pdfplumber no detecta nada), se
     usa un parser de patrón de línea sobre el texto plano de la página,
     basado en la estructura típica "CANTIDAD  DENOMINACIÓN DEL PUESTO  NIVEL"
     (un número al inicio, texto, un número al final). Esto también
     resuelve de forma natural las tablas que continúan en otra página sin
     repetir el encabezado, porque no depende de encontrar un encabezado:
     cada línea de cada página se evalúa por su propia forma.

En ambos casos se identifica la columna de "puesto"/"nivel"/"cantidad" por
el encabezado de la tabla (insensible a mayúsculas/acentos), no por
posición fija, para tolerar tablas con columnas en distinto orden.
"""
import os
import re
import sys
from typing import List, Optional, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from models.models import PuestoRecord, Fuente, Ubicacion, MetodoExtraccion  # noqa: E402
from normalization.normalizer import normalizar_puesto, normalizar_nivel, texto_parece_ruido  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger("word_extractor")

# Línea con forma "<cantidad> <denominación del puesto> <nivel>", que es la
# estructura típica de estas tablas cuando no se pueden extraer como tabla
# real (sin bordes visibles). Cantidad y nivel son números de 1-3 dígitos;
# el nombre del puesto debe tener al menos una letra (para no confundir
# líneas puramente numéricas, folios, fechas, etc.).
_PATRON_FILA_CON_CANTIDAD = re.compile(r"^\s*(\d{1,3})\s+(.*[A-Za-zÁÉÍÓÚÑáéíóúñ].*?)\s+(\d{1,3})\s*$")
# Variante sin columna de cantidad: "<denominación del puesto> <nivel>"
_PATRON_FILA_SIN_CANTIDAD = re.compile(r"^\s*(.*[A-Za-zÁÉÍÓÚÑáéíóúñ]{3,}.*?)\s+(\d{1,3})\s*$")


def _encontrar_indices_columnas(fila_encabezado: List[str]) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    """Regresa (idx_puesto, idx_nivel, idx_cantidad)."""
    idx_puesto, idx_nivel, idx_cantidad = None, None, None
    for i, celda in enumerate(fila_encabezado):
        texto_norm = normalizar_puesto(celda or "")
        # "nivel" y "cantidad" se evalúan antes que "puesto" porque
        # encabezados como "Nivel del puesto" contienen la palabra "puesto"
        # y se clasificarían mal si se revisara al revés.
        if idx_nivel is None and any(h in texto_norm for h in config.WORD_HEADERS_NIVEL):
            idx_nivel = i
        elif idx_cantidad is None and any(texto_norm == h or texto_norm.startswith(h + " ") for h in config.WORD_HEADERS_CANTIDAD):
            idx_cantidad = i
        elif idx_puesto is None and any(h in texto_norm for h in config.WORD_HEADERS_PUESTO):
            idx_puesto = i
    return idx_puesto, idx_nivel, idx_cantidad


def _procesar_tabla(filas: List[List[Optional[str]]], nombre_archivo: str,
                     tabla_index: int, metodo: MetodoExtraccion,
                     pagina: Optional[int] = None) -> List[PuestoRecord]:
    registros = []
    if not filas:
        return registros

    idx_puesto, idx_nivel, idx_cantidad = _encontrar_indices_columnas(filas[0])
    if idx_puesto is None:
        # esta tabla no parece contener columna de puesto -> se ignora completa
        return registros

    for fila_idx, fila in enumerate(filas[1:], start=2):  # fila 1 = encabezado
        if idx_puesto >= len(fila):
            continue
        valor_puesto = (fila[idx_puesto] or "").strip()
        valor_nivel = fila[idx_nivel].strip() if (idx_nivel is not None and idx_nivel < len(fila) and fila[idx_nivel]) else None
        valor_cantidad = fila[idx_cantidad].strip() if (idx_cantidad is not None and idx_cantidad < len(fila) and fila[idx_cantidad]) else None

        if texto_parece_ruido(valor_puesto, config.WORD_FILAS_IGNORAR_PATRONES):
            continue

        ubicacion = Ubicacion(
            archivo=nombre_archivo, pagina=pagina, tabla_index=tabla_index, fila_tabla=fila_idx,
        )

        registros.append(PuestoRecord(
            fuente=Fuente.WORD,
            puesto_original=valor_puesto,
            nivel_original=valor_nivel,
            puesto_normalizado=normalizar_puesto(valor_puesto),
            nivel_normalizado=normalizar_nivel(valor_nivel) if valor_nivel else None,
            ubicacion=ubicacion,
            metodo_extraccion=metodo,
            confianza_extraccion=1.0,
            cantidad=valor_cantidad,
        ))
    return registros


def _extraer_por_patron_de_linea(texto_pagina: str, nombre_archivo: str, pagina: int) -> List[PuestoRecord]:
    """
    Respaldo para cuando pdfplumber no detecta ninguna tabla en la página
    (tablas sin bordes visibles, muy comunes en documentos reales). Analiza
    cada línea de texto buscando la forma "<cantidad> <puesto> <nivel>" o,
    si no hay columna de cantidad, "<puesto> <nivel>".

    Se marca con confianza ligeramente reducida (0.9) porque es un método
    heurístico basado en patrón de texto, no en la estructura real de la
    tabla — para que quede identificable en el reporte y trazabilidad.
    """
    registros = []
    linea_pendiente = None
    num_linea_pendiente = None

    for num_linea, linea in enumerate(texto_pagina.splitlines(), start=1):
        linea = linea.strip()
        if not linea or texto_parece_ruido(linea, config.WORD_FILAS_IGNORAR_PATRONES):
            continue

        m = _PATRON_FILA_CON_CANTIDAD.match(linea)
        if not m and linea_pendiente is not None:
            linea_completa = f"{linea_pendiente} {linea}"
            m = _PATRON_FILA_CON_CANTIDAD.match(linea_completa)
            if m:
                linea = linea_completa
                num_linea = num_linea_pendiente
                linea_pendiente = None
                num_linea_pendiente = None

        if m and linea_pendiente is not None:
            linea_pendiente = None
            num_linea_pendiente = None

        if not m and linea_pendiente is None and re.match(r"^\d{1,3}\s+", linea):
            linea_pendiente = linea
            num_linea_pendiente = num_linea
            continue

        if m:
            cantidad, puesto, nivel = m.group(1), m.group(2).strip(), m.group(3)
        else:
            m = _PATRON_FILA_SIN_CANTIDAD.match(linea)
            if not m:
                continue
            cantidad, puesto, nivel = None, m.group(1).strip(), m.group(2)

        if texto_parece_ruido(puesto, config.WORD_FILAS_IGNORAR_PATRONES) or len(puesto) < 3:
            continue

        ubicacion = Ubicacion(
            archivo=nombre_archivo, pagina=pagina, fila_tabla=num_linea,
        )
        registros.append(PuestoRecord(
            fuente=Fuente.WORD,
            puesto_original=puesto,
            nivel_original=nivel,
            puesto_normalizado=normalizar_puesto(puesto),
            nivel_normalizado=normalizar_nivel(nivel),
            ubicacion=ubicacion,
            metodo_extraccion=MetodoExtraccion.TEXTO_DIRECTO,
            confianza_extraccion=0.9,
            cantidad=cantidad,
        ))

    return registros


def extraer_word_docx(ruta_archivo: str) -> List[PuestoRecord]:
    """Extrae de un .docx nativo. Preferido cuando está disponible."""
    import docx  # python-docx

    registros: List[PuestoRecord] = []
    nombre_archivo = os.path.basename(ruta_archivo)

    try:
        doc = docx.Document(ruta_archivo)
    except Exception as e:
        logger.error(f"No se pudo abrir el .docx '{ruta_archivo}': {e}")
        registros.append(PuestoRecord(
            fuente=Fuente.WORD, puesto_original="", nivel_original=None,
            ubicacion=Ubicacion(archivo=nombre_archivo),
            error=f".docx no legible o corrupto: {e}",
        ))
        return registros

    for tabla_index, tabla in enumerate(doc.tables, start=1):
        filas = [[celda.text for celda in fila.cells] for fila in tabla.rows]
        registros.extend(_procesar_tabla(
            filas, nombre_archivo, tabla_index, MetodoExtraccion.DOCX_NATIVO,
        ))

    logger.info(f"Word (.docx) '{nombre_archivo}': {len(registros)} registro(s) extraído(s) de {len(doc.tables)} tabla(s).")
    return registros


def extraer_word_pdf(ruta_archivo: str) -> List[PuestoRecord]:
    """Extrae de un PDF exportado desde Word, usando pdfplumber para tablas."""
    import pdfplumber

    registros: List[PuestoRecord] = []
    nombre_archivo = os.path.basename(ruta_archivo)

    try:
        pdf = pdfplumber.open(ruta_archivo)
    except Exception as e:
        logger.error(f"No se pudo abrir el PDF del Word '{ruta_archivo}': {e}")
        registros.append(PuestoRecord(
            fuente=Fuente.WORD, puesto_original="", nivel_original=None,
            ubicacion=Ubicacion(archivo=nombre_archivo),
            error=f"PDF no legible o corrupto: {e}",
        ))
        return registros

    tabla_global_index = 0
    for pagina_idx, page in enumerate(pdf.pages, start=1):
        texto_pagina = page.extract_text() or ""
        if len(texto_pagina.strip()) < 5:
            logger.warning(
                f"Página {pagina_idx} del Word/PDF parece escaneada (sin texto). "
                f"Este extractor no aplica OCR sobre tablas; considera exportar/reconvertir el documento."
            )
            continue

        tablas = page.extract_tables()
        registros_pagina: List[PuestoRecord] = []
        for tabla in tablas:
            tabla_global_index += 1
            filas_limpias = [[(c or "").strip() for c in fila] for fila in tabla]
            registros_pagina.extend(_procesar_tabla(
                filas_limpias, nombre_archivo, tabla_global_index,
                MetodoExtraccion.TEXTO_DIRECTO, pagina=pagina_idx,
            ))

        if not registros_pagina:
            # Ninguna tabla detectada por líneas dio resultados utilizables
            # en esta página (probablemente no tiene bordes visibles, o es
            # una continuación de tabla sin encabezado propio). Se intenta
            # el respaldo de patrón de línea antes de dar la página por vacía.
            registros_pagina = _extraer_por_patron_de_linea(texto_pagina, nombre_archivo, pagina_idx)
            if registros_pagina:
                logger.info(
                    f"Página {pagina_idx}: sin tablas con bordes detectables; "
                    f"se usó respaldo por patrón de línea ({len(registros_pagina)} fila(s))."
                )

        registros.extend(registros_pagina)

    pdf.close()
    logger.info(f"Word (PDF) '{nombre_archivo}': {len(registros)} registro(s) extraído(s).")
    return registros


def extraer_word(ruta_archivo: str) -> List[PuestoRecord]:
    """
    Punto de entrada único: decide automáticamente la estrategia según la
    extensión del archivo. Si se dispone del .docx original, se prefiere
    sobre el PDF (más confiable, ver análisis inicial).
    """
    extension = os.path.splitext(ruta_archivo)[1].lower()
    if extension == ".docx":
        return extraer_word_docx(ruta_archivo)
    elif extension == ".pdf":
        return extraer_word_pdf(ruta_archivo)
    else:
        raise ValueError(f"Extensión no soportada para el extractor de Word: {extension}")
