"""
Normalización de texto para puestos y niveles.

Regla de oro: NUNCA modificar el valor original. Estas funciones siempre
reciben un string y regresan un string normalizado nuevo; el original se
conserva por separado en PuestoRecord.puesto_original / nivel_original.
"""
import re
import sys
import os
import unicodedata
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402


def _quitar_acentos(texto: str) -> str:
    """Quita acentos y diéresis conservando la letra base (á -> a, ü -> u)."""
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _normalizar_comillas_y_guiones(texto: str) -> str:
    # Distintos tipos de comillas -> comilla simple estándar
    comillas = ["\u2018", "\u2019", "\u201c", "\u201d", "´", "`", '"', "'"]
    for c in comillas:
        texto = texto.replace(c, "")
    # Distintos tipos de guion -> guion estándar
    guiones = ["\u2013", "\u2014", "\u2012", "\u2010", "‑"]
    for g in guiones:
        texto = texto.replace(g, "-")
    return texto


def normalizar_puesto(texto: str) -> str:
    """
    Normaliza el nombre de un puesto para comparación.
    - Minúsculas
    - Sin acentos/diéresis
    - Sin comillas, comillas tipográficas
    - Guiones estandarizados y espacios alrededor de guiones colapsados
    - Espacios múltiples, tabs y saltos de línea colapsados a uno solo
    - Sin espacios al inicio/fin
    """
    if texto is None:
        return ""
    t = str(texto)

    # saltos de línea y tabs -> espacio
    t = re.sub(r"[\r\n\t]+", " ", t)

    t = _normalizar_comillas_y_guiones(t)
    t = _quitar_acentos(t)
    t = t.lower()

    # espacios alrededor de guiones: "director - general" -> "director-general"
    t = re.sub(r"\s*-\s*", "-", t)

    # caracteres especiales no alfanuméricos (excepto guion y espacio) fuera
    t = re.sub(r"[^\w\s\-]", "", t, flags=re.UNICODE)

    # colapsar espacios múltiples
    t = re.sub(r"\s+", " ", t)

    return t.strip()


def normalizar_nivel(texto) -> str:
    """
    Normaliza una representación de nivel a un formato canónico: "N{numero}".
    Acepta: "8", "Nivel 8", "NIVEL 8", "N-8", "Nvl. 8", 8 (int), 8.0 (float).
    Si no se puede extraer un número, regresa "" (nivel no reconocido).
    """
    if texto is None:
        return ""
    if isinstance(texto, (int, float)):
        # Excel a veces trae el nivel como número puro
        numero = int(texto)
        return f"N{numero}"

    t = str(texto).strip()
    if not t:
        return ""

    t_lower = _quitar_acentos(t.lower())
    for patt in config.NIVEL_NORMALIZACION_PATTERNS:
        t_lower = re.sub(patt, "", t_lower)

    match = re.search(r"\d+", t_lower)
    if not match:
        return ""
    return f"N{int(match.group())}"


def detectar_abreviaturas_en_texto(puesto_normalizado: str) -> list:
    """
    Regresa la lista de tokens de `puesto_normalizado` que son abreviaturas
    conocidas (claves de config.ABREVIATURAS_PUESTO). Se usa para poder
    mostrar en el reporte EXACTAMENTE qué equivalencia institucional se
    aplicó (ej. "J.U.D. → jefatura de unidad departamental"), no solo que
    "hubo una coincidencia por normalización".
    """
    if not puesto_normalizado:
        return []
    return [p for p in puesto_normalizado.split() if p in config.ABREVIATURAS_PUESTO]


def expandir_abreviaturas(texto_normalizado: str) -> str:
    """
    Expande abreviaturas comunes (config.ABREVIATURAS_PUESTO) dentro de un
    texto YA normalizado. Se usa exclusivamente para construir la CLAVE DE
    COMPARACIÓN entre fuentes (ver comparison/comparator.py); nunca se aplica
    al texto original ni al puesto_normalizado que se muestra en el reporte,
    para no perder trazabilidad de lo que realmente decía cada documento.

    Solo reemplaza tokens completos (palabra exacta), nunca substrings
    dentro de otra palabra, para evitar expansiones incorrectas.
    """
    if not texto_normalizado:
        return texto_normalizado
    palabras = texto_normalizado.split()
    expandido = [config.ABREVIATURAS_PUESTO.get(p, p) for p in palabras]
    return " ".join(expandido)


def normalizar_para_comparacion(puesto_normalizado: str) -> str:
    """Clave usada para EMPAREJAR puestos entre fuentes distintas (ver comparator.py)."""
    return expandir_abreviaturas(puesto_normalizado)


_PATRON_ACRONIMO_CON_PUNTOS = re.compile(r"^([A-ZÁÉÍÓÚÑ]\.){2,6}$")
_PATRON_ACRONIMO_SIN_PUNTOS = re.compile(r"^[A-ZÁÉÍÓÚÑ]{2,6}$")


def detectar_posible_abreviatura_no_reconocida(puesto_original: str) -> Optional[str]:
    """
    Heurística CONSERVADORA (solo advertencia, nunca bloquea nada) para
    detectar tokens que TIENEN FORMA de abreviatura/acrónimo institucional
    (ej. "C.P.A.", "DGCOP") pero no están en config.ABREVIATURAS_PUESTO.
    Se usa para señalar "⚠️ abreviatura no reconocida" en el reporte, para
    que el usuario decida si debe agregarse al catálogo — nunca se asume
    su significado automáticamente.

    Solo evalúa el PRIMER token del puesto (donde suelen ir las
    abreviaturas de tipo de puesto), para minimizar falsos positivos con
    siglas que son parte del nombre de un área (ej. "TI", "SAT").
    """
    if not puesto_original:
        return None
    primer_token = puesto_original.strip().split()[0] if puesto_original.strip() else ""
    if not primer_token:
        return None

    parece_abreviatura = bool(
        _PATRON_ACRONIMO_CON_PUNTOS.match(primer_token)
        or _PATRON_ACRONIMO_SIN_PUNTOS.match(primer_token)
    )
    if not parece_abreviatura:
        return None

    clave_normalizada = normalizar_puesto(primer_token)
    if clave_normalizada in config.ABREVIATURAS_PUESTO:
        return None  # es una abreviatura reconocida, no hace falta advertir

    return f"'{primer_token}' parece una abreviatura pero no está en el catálogo de equivalencias (config.ABREVIATURAS_PUESTO)."


def es_nivel_valido(nivel_normalizado: str) -> bool:
    return bool(nivel_normalizado) and re.fullmatch(r"N\d+", nivel_normalizado) is not None


def texto_parece_ruido(texto: str, patrones_ignorar) -> bool:
    """
    Determina si un texto de fila/bloque parece ser ruido administrativo
    (títulos, pies de página, etc.) y no un puesto real.
    """
    if not texto or not texto.strip():
        return True
    t_norm = normalizar_puesto(texto)
    for patt in patrones_ignorar:
        if re.search(patt, t_norm, flags=re.IGNORECASE):
            return True
    return False
