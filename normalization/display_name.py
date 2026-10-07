"""Homologación para presentación; no modifica las claves de comparación."""
import re


_PREFIJOS = (
    (re.compile(r"^\s*(?:jefatura\s+de\s+unidad\s+departamental|jefe\s+de\s+unidad\s+departamental|j\.?\s*u\.?\s*d\.?)(?=\s|$)", re.IGNORECASE), "J.U.D."),
    (re.compile(r"^\s*(?:l[íi]der\s+coordinador\s+de\s+proyectos|l\.?\s*c\.?\s*p\.?)(?=\s|$)", re.IGNORECASE), "L.C.P."),
)


def homologar_puesto_excel(texto: str) -> str:
    """Abrevia únicamente el tipo al inicio y conserva el resto del nombre."""
    for patron, abreviatura in _PREFIJOS:
        match = patron.match(texto)
        if match:
            resto = texto[match.end():].lstrip()
            return abreviatura + (" " + resto if resto else "")
    return texto
