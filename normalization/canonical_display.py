"""Representación canónica legible de puestos para el reporte.

La comparación interna sigue usando nombres expandidos y normalizados porque
es más robusta para fuzzy matching y reglas institucionales. Esta capa solo
transforma la representación visible en el Excel de resultados, conservando
los valores originales de cada fuente.
"""
import re


_CONECTORES_MINUSCULA = {
    "a", "al", "con", "de", "del", "e", "el", "en", "la", "las",
    "los", "para", "por", "y",
}

_PATRONES_ABREVIACION = (
    (
        "J.U.D.",
        re.compile(
            r"^\s*(?:j\s*\.?\s*u\s*\.?\s*d\s*\.?|jefatura\s+de\s+unidad\s+departamental)"
            r"(?=\s|$|[-:])\s*[-:]?\s*",
            flags=re.IGNORECASE,
        ),
    ),
    (
        "L.C.P.",
        re.compile(
            r"^\s*(?:l\s*\.?\s*c\s*\.?\s*p\s*\.?|l[ií]der\s+coordinador\s+de\s+proyectos)"
            r"(?=\s|$|[-:])\s*[-:]?\s*",
            flags=re.IGNORECASE,
        ),
    ),
)


def _limpiar_espacios(texto: str) -> str:
    """Colapsa saltos, tabs y espacios sin alterar acentos ni contenido."""
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def _formatear_token(token: str) -> str:
    """Da formato legible sin destruir siglas cortas ni conectores."""
    if not token:
        return token

    match = re.match(r"^([^\wÁÉÍÓÚÑÜáéíóúñü]*)(.*?)([^\wÁÉÍÓÚÑÜáéíóúñü]*)$", token)
    if not match:
        return token

    prefijo, nucleo, sufijo = match.groups()
    if not nucleo:
        return token

    minuscula = nucleo.lower()
    if minuscula in _CONECTORES_MINUSCULA:
        formateado = minuscula
    elif nucleo.isupper() and len(nucleo) <= 4:
        # Conserva siglas reales como TI, RH, TIC, etc.
        formateado = nucleo
    elif nucleo.isupper() or nucleo.islower():
        formateado = minuscula[:1].upper() + minuscula[1:]
    else:
        # Si ya viene con capitalización mixta razonable, se conserva.
        formateado = nucleo

    return f"{prefijo}{formateado}{sufijo}"


def _formatear_resto(texto: str) -> str:
    limpio = _limpiar_espacios(texto)
    if not limpio:
        return ""
    return " ".join(_formatear_token(token) for token in limpio.split(" "))


def abreviar_puesto_canonico(texto: str) -> str:
    """
    Devuelve una representación canónica y legible para mostrar en reportes.

    Ejemplos:
      - Jefatura de Unidad Departamental de Recursos Humanos
        -> J.U.D. de Recursos Humanos
      - JUD DE RECURSOS HUMANOS
        -> J.U.D. de Recursos Humanos
      - Líder Coordinador de Proyectos de Planeación
        -> L.C.P. de Planeación

    Solo J.U.D. y L.C.P. se transforman. Los demás puestos conservan su texto
    original, salvo limpieza de espacios. La clave interna usada para comparar
    no se modifica aquí.
    """
    limpio = _limpiar_espacios(texto)
    if not limpio:
        return ""

    for sigla, patron in _PATRONES_ABREVIACION:
        match = patron.match(limpio)
        if not match:
            continue

        resto = limpio[match.end():].strip()
        resto_formateado = _formatear_resto(resto)
        return f"{sigla} {resto_formateado}".strip()

    return limpio
