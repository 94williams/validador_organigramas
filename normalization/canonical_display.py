"""Representación canónica legible de puestos para el reporte.

La comparación interna sigue usando nombres expandidos porque es más robusta
para fuzzy matching y reglas institucionales. Esta capa solo transforma la
representación que se muestra en el Excel de resultados, conservando los
valores originales de cada fuente.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from normalization.normalizer import normalizar_puesto, expandir_abreviaturas  # noqa: E402


# Solo estas categorías deben mostrarse de forma abreviada para asimilar el
# nombre al formato habitual del organigrama. La expansión oficial permanece
# centralizada en config.ABREVIATURAS_PUESTO.
_TOKENS_CANONICOS_ABREVIADOS = ("jud", "lcp")


def _formatear_sigla(token: str) -> str:
    """Convierte ``jud`` en ``J.U.D.`` y ``lcp`` en ``L.C.P.``."""
    return ".".join(token.upper()) + "."


def abreviar_puesto_canonico(texto: str) -> str:
    """
    Devuelve una representación canónica para mostrar en reportes.

    Ejemplos:
      - Jefatura de Unidad Departamental de Recursos Humanos
        -> J.U.D. de recursos humanos
      - Líder Coordinador de Proyectos de Planeación
        -> L.C.P. de planeacion

    La función acepta tanto la forma completa como JUD/LCP con o sin puntos.
    No modifica ``puesto_original`` ni la clave interna usada para comparar.
    """
    if texto is None:
        return ""

    normalizado = normalizar_puesto(texto)
    expandido = expandir_abreviaturas(normalizado)

    for token in _TOKENS_CANONICOS_ABREVIADOS:
        nombre_completo = config.ABREVIATURAS_PUESTO[token]
        sigla = _formatear_sigla(token)

        if expandido == nombre_completo:
            return sigla

        prefijo = nombre_completo + " "
        if expandido.startswith(prefijo):
            resto = expandido[len(prefijo):].strip()
            return f"{sigla} {resto}" if resto else sigla

    return expandido
