"""
Utilidades comunes para trabajar con PDFs:
- Detectar si una página tiene texto seleccionable o es escaneada.
- Ejecutar OCR página por página solo cuando es necesario.

Se usa PyMuPDF (fitz) porque:
- Es mucho más rápido que pdfplumber para extraer texto/bloques crudos.
- Da bounding boxes de bloques de texto, útil para el organigrama.
- Permite rasterizar páginas a imagen para el OCR sin depender de poppler.

pdfplumber se reserva para el extractor de tablas del Word/PDF (extractors/word_extractor.py),
porque su detección de líneas de tabla es más confiable que la de PyMuPDF.
"""
import os
import sys
from typing import List, Tuple

import fitz  # PyMuPDF

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger("pdf_utils")

MIN_CARACTERES_PARA_CONSIDERAR_TEXTO = 15  # por página, umbral heurístico


def pagina_tiene_texto(page: "fitz.Page") -> bool:
    texto = page.get_text("text")
    return len(texto.strip()) >= MIN_CARACTERES_PARA_CONSIDERAR_TEXTO


def abrir_pdf(ruta_archivo: str) -> fitz.Document:
    return fitz.open(ruta_archivo)


def ocr_pagina(page: "fitz.Page") -> str:
    """
    Rasteriza la página y le aplica OCR con Tesseract.
    Se importa pytesseract/PIL de forma perezosa para no forzar la
    dependencia si el usuario nunca tiene PDFs escaneados.
    """
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError as e:
        raise RuntimeError(
            "OCR requerido pero pytesseract/Pillow no están instalados. "
            "Instala con: pip install pytesseract pillow"
        ) from e

    zoom = config.OCR_DPI / 72
    matriz = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matriz)
    img = Image.open(io.BytesIO(pix.tobytes("png")))

    texto = pytesseract.image_to_string(img, lang=config.OCR_IDIOMA)
    return texto


def extraer_texto_pagina(page: "fitz.Page") -> Tuple[str, str, float]:
    """
    Regresa (texto, metodo, confianza) para una página:
    - Si tiene texto seleccionable: extracción directa, confianza 1.0
    - Si no: OCR, confianza config.OCR_CONFIANZA_DEFECTO
    """
    if pagina_tiene_texto(page):
        return page.get_text("text"), "texto_directo", 1.0

    logger.info(f"Página {page.number + 1}: sin texto seleccionable, aplicando OCR.")
    try:
        texto_ocr = ocr_pagina(page)
        return texto_ocr, "OCR", config.OCR_CONFIANZA_DEFECTO
    except Exception as e:
        logger.error(f"OCR falló en página {page.number + 1}: {e}")
        return "", "error_ocr", 0.0


def obtener_bloques_texto(page: "fitz.Page") -> List[dict]:
    """
    Regresa los bloques de texto de una página con su bounding box, usando
    la extracción nativa de PyMuPDF (dict mode). Cada bloque:
    {"texto": str, "bbox": (x0, y0, x1, y1)}
    Solo válido si la página tiene texto seleccionable (para PDFs escaneados
    se debe usar OCR con datos de posición, ver ocr_pagina_con_posiciones).
    """
    data = page.get_text("dict")
    bloques = []
    for block in data.get("blocks", []):
        if block.get("type") != 0:  # 0 = texto, 1 = imagen
            continue
        lineas_texto = []
        for line in block.get("lines", []):
            texto_linea = "".join(span.get("text", "") for span in line.get("spans", []))
            if texto_linea.strip():
                lineas_texto.append(texto_linea.strip())
        if lineas_texto:
            bloques.append({
                "texto": "\n".join(lineas_texto),
                "bbox": tuple(block.get("bbox")),
            })
    return bloques


def ocr_pagina_con_posiciones(page: "fitz.Page") -> List[dict]:
    """
    OCR con posiciones aproximadas por palabra/línea, usando
    pytesseract.image_to_data. Se agrupa por línea de OCR para aproximar
    un "bloque" comparable al de obtener_bloques_texto.
    """
    try:
        import pytesseract
        from PIL import Image
        import io
    except ImportError as e:
        raise RuntimeError("OCR requerido pero pytesseract/Pillow no están instalados.") from e

    zoom = config.OCR_DPI / 72
    matriz = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matriz)
    img = Image.open(io.BytesIO(pix.tobytes("png")))

    data = pytesseract.image_to_data(
        img, lang=config.OCR_IDIOMA, output_type=pytesseract.Output.DICT
    )

    lineas = {}
    n = len(data["text"])
    for i in range(n):
        texto = data["text"][i].strip()
        if not texto:
            continue
        clave_linea = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
        # convertir coords de imagen (a `zoom` dpi) a coords de página PDF
        x0, y0, x1, y1 = x / zoom, y / zoom, (x + w) / zoom, (y + h) / zoom
        if clave_linea not in lineas:
            lineas[clave_linea] = {"palabras": [], "bbox": [x0, y0, x1, y1]}
        lineas[clave_linea]["palabras"].append(texto)
        bbox = lineas[clave_linea]["bbox"]
        bbox[0] = min(bbox[0], x0)
        bbox[1] = min(bbox[1], y0)
        bbox[2] = max(bbox[2], x1)
        bbox[3] = max(bbox[3], y1)

    bloques = []
    for info in lineas.values():
        bloques.append({
            "texto": " ".join(info["palabras"]),
            "bbox": tuple(info["bbox"]),
        })
    return bloques
