"""
Extractor del organigrama (PDF exportado desde Visio).

Estrategia (ver análisis y ajustes tras probar con un organigrama real):

MÉTODO PRINCIPAL — cajas vectoriales:
Los organigramas de Visio casi siempre dibujan cada puesto como un
rectángulo con borde. PyMuPDF puede leer esos trazos vectoriales
directamente (page.get_drawings()), así que en vez de adivinar
agrupaciones por cercanía de texto, se usan los bordes REALES de cada
caja para decidir qué texto pertenece a qué puesto. Esto es mucho más
robusto en organigramas densos con muchas columnas, donde agrupar solo
por proximidad puede fusionar cajas vecinas.

Además, es común que el texto dentro de cada caja esté duplicado (una
copia "visible" y otra de una capa de accesibilidad/exportación), y que
el nivel aparezca como un número suelto en vez de "Nivel X". Todo esto
se maneja en `_limpiar_texto_caja`.

MÉTODO DE RESPALDO — agrupación espacial por cercanía:
Si una página no tiene cajas vectoriales detectables (organigramas
dibujados de otra forma, o el PDF no expone los trazos), se usa el
método anterior de agrupar bloques de texto por cercanía relativa.

Para páginas escaneadas (sin texto seleccionable), se aplica OCR y se
usa el método de agrupación por cercanía sobre las posiciones que
entrega el propio OCR.
"""
import os
import re
import statistics
import sys
from typing import List, Optional, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from models.models import PuestoRecord, Fuente, Ubicacion, MetodoExtraccion  # noqa: E402
from normalization.normalizer import normalizar_puesto, normalizar_nivel, texto_parece_ruido  # noqa: E402
from extractors.pdf_utils import (  # noqa: E402
    abrir_pdf, pagina_tiene_texto, obtener_bloques_texto, ocr_pagina_con_posiciones,
)
from utils.logger import get_logger  # noqa: E402

logger = get_logger("organigrama_extractor")

_PATRONES_NIVEL_COMPILADOS = [re.compile(p, re.IGNORECASE) for p in config.NIVEL_PATTERNS]
_PATRON_TOKEN_NUMERICO = re.compile(r"\d{1,3}")


# ---------------------------------------------------------------------------
# MÉTODO PRINCIPAL: cajas vectoriales
# ---------------------------------------------------------------------------

def _rects_cercanos(a: tuple, b: tuple, tolerancia: float) -> bool:
    return all(abs(a[i] - b[i]) <= tolerancia for i in range(4))


def _rect_contiene(a: tuple, b: tuple) -> bool:
    return a[0] <= b[0] + 1 and a[1] <= b[1] + 1 and a[2] >= b[2] - 1 and a[3] >= b[3] - 1 and a != b


def _obtener_cajas_vectoriales(page) -> List[Tuple[float, float, float, float]]:
    """
    Detecta las cajas (rectángulos) de puestos en una página, filtrando
    bordes de página completos y paneles grandes de metadatos por su área
    relativa a la mediana de la página.
    """
    drawings = page.get_drawings()
    rects_crudos = [
        (r.x0, r.y0, r.x1, r.y1)
        for r in (d.get("rect") for d in drawings)
        if r and (r.x1 - r.x0) > 5 and (r.y1 - r.y0) > 5
    ]
    if not rects_crudos:
        return []

    unicos: List[tuple] = []
    for r in rects_crudos:
        if not any(_rects_cercanos(r, u, config.ORGANIGRAMA_RECT_DEDUPE_TOLERANCIA) for u in unicos):
            unicos.append(r)

    areas = [(x1 - x0) * (y1 - y0) for x0, y0, x1, y1 in unicos]
    mediana = statistics.median(areas)

    cajas = [
        r for r in unicos
        if config.ORGANIGRAMA_AREA_RATIO_MIN * mediana <= (r[2] - r[0]) * (r[3] - r[1]) <= config.ORGANIGRAMA_AREA_RATIO_MAX * mediana
    ]
    return [c for c in cajas if not any(_rect_contiene(c, otra) for otra in cajas)]


def _obtener_lineas_con_posicion(page) -> List[Tuple[str, tuple]]:
    data = page.get_text("dict")
    lineas = []
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            texto_linea = "".join(s.get("text", "") for s in line.get("spans", [])).strip()
            if texto_linea:
                lineas.append((texto_linea, tuple(line.get("bbox"))))
    return lineas


def _centro(bbox: tuple) -> Tuple[float, float]:
    return ((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)


def _punto_dentro_de_caja(caja: tuple, punto: tuple, margen: float = 2) -> bool:
    x0, y0, x1, y1 = caja
    return (x0 - margen) <= punto[0] <= (x1 + margen) and (y0 - margen) <= punto[1] <= (y1 + margen)


def _limpiar_texto_caja(texto_crudo: str) -> Tuple[str, Optional[str]]:
    """
    Limpia el texto crudo de una caja del organigrama:
    - Extrae el nivel, ya sea en formato "Nivel X"/"N-X" o como número suelto.
    - Si el texto viene duplicado (típico de la capa de accesibilidad de
      Visio: el nombre y el nivel aparecen dos veces seguidas), colapsa la
      duplicación.
    - Si el nombre del puesto también contiene un número (ej. "Zona 1",
      "Zona 2"), ese número NO se confunde con el nivel: se prioriza como
      nivel cualquier token numérico que aparezca en el catálogo oficial de
      niveles válidos (config.NIVELES_VALIDOS_CONOCIDOS); los demás números
      se conservan como parte del nombre del puesto.
    Regresa (puesto_limpio, nivel_o_None).
    """
    texto_trabajo = texto_crudo
    niveles_de_patron = []

    for patt in _PATRONES_NIVEL_COMPILADOS[:-1]:
        for m in patt.finditer(texto_trabajo):
            niveles_de_patron.append(m.group(0))
        texto_trabajo = patt.sub(" ", texto_trabajo)

    palabras = texto_trabajo.split()
    niveles_validos_conocidos = set(config.NIVELES_VALIDOS_CONOCIDOS)

    if niveles_de_patron:
        # ya se encontró un nivel explícito tipo "Nivel X"; los números
        # sueltos restantes (si los hay) se tratan como parte del nombre.
        nivel = niveles_de_patron[0]
        resto = palabras
    else:
        tokens_numericos = [p for p in palabras if _PATRON_TOKEN_NUMERICO.fullmatch(p)]
        # preferir, entre los números encontrados, uno que sea un nivel
        # oficialmente válido; si ninguno lo es, usar el primero (comportamiento
        # anterior, para organigramas sin catálogo configurado).
        candidato_valido = next(
            (t for t in tokens_numericos if int(t) in niveles_validos_conocidos), None,
        )
        nivel = candidato_valido if candidato_valido is not None else (tokens_numericos[0] if tokens_numericos else None)

        if nivel is not None:
            # se retira SOLO el token exacto elegido como nivel (en todas sus
            # apariciones, una por cada copia duplicada del texto); cualquier
            # otro número (ej. "Zona 1") permanece como parte del nombre.
            resto = [p for p in palabras if p != nivel]
        else:
            resto = palabras

    n = len(resto)
    if n >= 2 and n % 2 == 0 and resto[: n // 2] == resto[n // 2:]:
        resto = resto[: n // 2]

    return " ".join(resto).strip(), nivel


def _texto_es_ruido_organigrama(texto: str) -> bool:
    if not texto or len(texto.strip()) < 2:
        return True
    t = normalizar_puesto(texto)
    return any(re.search(p, t, re.IGNORECASE) for p in config.ORGANIGRAMA_TEXTO_IGNORAR_PATRONES)


def _extraer_pagina_por_cajas(page, nombre_archivo: str, num_pagina: int) -> Optional[List[PuestoRecord]]:
    """Regresa None si la página no tiene cajas vectoriales (se debe usar el respaldo)."""
    cajas = _obtener_cajas_vectoriales(page)
    if not cajas:
        return None

    lineas = _obtener_lineas_con_posicion(page)
    registros: List[PuestoRecord] = []

    for caja in cajas:
        lineas_en_caja = [t for t, bbox in lineas if _punto_dentro_de_caja(caja, _centro(bbox))]
        if not lineas_en_caja:
            continue

        texto_crudo = " ".join(lineas_en_caja)
        puesto, nivel = _limpiar_texto_caja(texto_crudo)

        if not puesto or len(puesto) < 2 or _texto_es_ruido_organigrama(puesto):
            continue

        ubicacion = Ubicacion(
            archivo=nombre_archivo, pagina=num_pagina,
            posicion_aprox=f"x={caja[0]:.0f},y={caja[1]:.0f}",
            bbox=caja,
        )
        registros.append(PuestoRecord(
            fuente=Fuente.ORGANIGRAMA,
            puesto_original=puesto,
            nivel_original=nivel,
            puesto_normalizado=normalizar_puesto(puesto),
            nivel_normalizado=normalizar_nivel(nivel) if nivel else None,
            ubicacion=ubicacion,
            metodo_extraccion=MetodoExtraccion.TEXTO_DIRECTO,
            confianza_extraccion=1.0,
        ))

    logger.info(f"Página {num_pagina}: {len(cajas)} caja(s) vectorial(es) detectada(s), {len(registros)} puesto(s) extraído(s).")
    return registros


# ---------------------------------------------------------------------------
# MÉTODO DE RESPALDO: agrupación espacial por cercanía de texto
# ---------------------------------------------------------------------------

def _extraer_nivel_de_texto(texto: str):
    for patt in _PATRONES_NIVEL_COMPILADOS:
        m = patt.search(texto)
        if m:
            nivel_str = m.group(0)
            resto = (texto[:m.start()] + texto[m.end():]).strip()
            return nivel_str, resto
    return None, texto


def _agrupar_bloques_por_cercania(bloques: List[dict], alto_pagina: float) -> List[List[dict]]:
    if not bloques:
        return []
    bloques_ordenados = sorted(bloques, key=lambda b: (b["bbox"][1], b["bbox"][0]))
    margen = alto_pagina * config.ORGANIGRAMA_AGRUPACION_DISTANCIA_RELATIVA

    grupos: List[List[dict]] = []
    usados = [False] * len(bloques_ordenados)

    for i, b in enumerate(bloques_ordenados):
        if usados[i]:
            continue
        grupo = [b]
        usados[i] = True
        x0, y0, x1, y1 = b["bbox"]

        cambiado = True
        while cambiado:
            cambiado = False
            for j, b2 in enumerate(bloques_ordenados):
                if usados[j]:
                    continue
                bx0, by0, bx1, by1 = b2["bbox"]
                cerca_verticalmente = (by0 - y1 <= margen) and (by0 - y1 >= -margen * 3)
                solapa_horizontalmente = not (bx1 < x0 - margen * 4 or bx0 > x1 + margen * 4)
                if cerca_verticalmente and solapa_horizontalmente:
                    grupo.append(b2)
                    usados[j] = True
                    x0, y0, x1, y1 = (min(x0, bx0), min(y0, by0), max(x1, bx1), max(y1, by1))
                    cambiado = True
        grupos.append(grupo)
    return grupos


def _extraer_pagina_por_cercania(page, nombre_archivo: str, num_pagina: int, bloques: List[dict],
                                  metodo: MetodoExtraccion, confianza_base: float) -> List[PuestoRecord]:
    alto_pagina = page.rect.height
    grupos = _agrupar_bloques_por_cercania(bloques, alto_pagina)
    logger.info(f"Página {num_pagina}: sin cajas vectoriales, usando respaldo por cercanía "
                f"({len(bloques)} bloque(s) -> {len(grupos)} caja(s) candidatas).")

    registros: List[PuestoRecord] = []
    for grupo in grupos:
        texto_completo = " ".join(b["texto"].replace("\n", " ") for b in grupo).strip()
        if texto_parece_ruido(texto_completo, [r"^p[aá]gina\s*\d+", r"^\s*$"]) or _texto_es_ruido_organigrama(texto_completo):
            continue

        nivel_str, texto_puesto = _extraer_nivel_de_texto(texto_completo)
        if not texto_puesto or len(texto_puesto.strip()) < 2:
            continue

        xs = [b["bbox"][0] for b in grupo]
        ys = [b["bbox"][1] for b in grupo]
        xe = [b["bbox"][2] for b in grupo]
        ye = [b["bbox"][3] for b in grupo]
        bbox_grupo = (min(xs), min(ys), max(xe), max(ye))

        ubicacion = Ubicacion(
            archivo=nombre_archivo, pagina=num_pagina,
            posicion_aprox=f"x={bbox_grupo[0]:.0f},y={bbox_grupo[1]:.0f}",
            bbox=bbox_grupo,
        )
        registros.append(PuestoRecord(
            fuente=Fuente.ORGANIGRAMA,
            puesto_original=texto_puesto.strip(),
            nivel_original=nivel_str,
            puesto_normalizado=normalizar_puesto(texto_puesto),
            nivel_normalizado=normalizar_nivel(nivel_str) if nivel_str else None,
            ubicacion=ubicacion,
            metodo_extraccion=metodo,
            confianza_extraccion=confianza_base,
        ))
    return registros


# ---------------------------------------------------------------------------
# PUNTO DE ENTRADA
# ---------------------------------------------------------------------------

def extraer_organigrama(ruta_archivo: str) -> List[PuestoRecord]:
    registros: List[PuestoRecord] = []
    nombre_archivo = os.path.basename(ruta_archivo)

    try:
        doc = abrir_pdf(ruta_archivo)
    except Exception as e:
        logger.error(f"No se pudo abrir el PDF del organigrama '{ruta_archivo}': {e}")
        registros.append(PuestoRecord(
            fuente=Fuente.ORGANIGRAMA, puesto_original="", nivel_original=None,
            ubicacion=Ubicacion(archivo=nombre_archivo),
            error=f"PDF no legible o corrupto: {e}",
        ))
        return registros

    for page in doc:
        num_pagina = page.number + 1

        if pagina_tiene_texto(page):
            resultado_cajas = None
            if config.ORGANIGRAMA_USAR_CAJAS_VECTORIALES:
                try:
                    resultado_cajas = _extraer_pagina_por_cajas(page, nombre_archivo, num_pagina)
                except Exception as e:
                    logger.warning(f"Página {num_pagina}: falló la detección de cajas vectoriales ({e}), usando respaldo.")
                    resultado_cajas = None

            if resultado_cajas is not None:
                registros.extend(resultado_cajas)
            else:
                bloques = obtener_bloques_texto(page)
                registros.extend(_extraer_pagina_por_cercania(
                    page, nombre_archivo, num_pagina, bloques,
                    MetodoExtraccion.TEXTO_DIRECTO, 1.0,
                ))
        else:
            logger.info(f"Página {num_pagina} del organigrama sin texto seleccionable, aplicando OCR.")
            try:
                bloques = ocr_pagina_con_posiciones(page)
                registros.extend(_extraer_pagina_por_cercania(
                    page, nombre_archivo, num_pagina, bloques,
                    MetodoExtraccion.OCR, config.OCR_CONFIANZA_DEFECTO,
                ))
            except Exception as e:
                logger.error(f"OCR falló en página {num_pagina} del organigrama: {e}")
                registros.append(PuestoRecord(
                    fuente=Fuente.ORGANIGRAMA, puesto_original="", nivel_original=None,
                    ubicacion=Ubicacion(archivo=nombre_archivo, pagina=num_pagina),
                    error=f"Fallo de OCR en página {num_pagina}: {e}",
                    metodo_extraccion=MetodoExtraccion.OCR,
                ))

    doc.close()
    logger.info(f"Organigrama '{nombre_archivo}': {len(registros)} registro(s) extraído(s) en total.")
    return registros
