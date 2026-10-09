"""Homologación de denominaciones J.U.D. y L.C.P. en todas las fuentes."""
import re


_PREFIJOS = (
    (re.compile(r"^\s*(?:jefatura\s+de\s+unidad\s+departamental|jefe\s+de\s+unidad\s+departamental|j\.?\s*u\.?\s*d\.?)(?=\s|$)", re.IGNORECASE), "J.U.D."),
    (re.compile(r"^\s*(?:l[íi]der\s+coordinador\s+de\s+proyectos|l\.?\s*c\.?\s*p\.?)(?=\s|$)", re.IGNORECASE), "L.C.P."),
)


def homologar_puesto(texto: str) -> str:
    """Abrevia únicamente el tipo al inicio y conserva el resto del nombre."""
    for patron, abreviatura in _PREFIJOS:
        match = patron.match(texto)
        if match:
            resto = texto[match.end():].lstrip()
            return abreviatura + (" " + resto if resto else "")
    return texto


# Alias para consumidores existentes.
homologar_puesto_excel = homologar_puesto
