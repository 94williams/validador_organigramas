"""
Funciones de comparación entre dos textos normalizados de puesto.
Implementa los 3 niveles descritos en el análisis:
  1. Exacta (sobre el original)
  2. Normalizada (sobre el texto normalizado)
  3. Fuzzy (similitud aproximada + reglas de jerarquía)
"""
import os
import re
import sys

from rapidfuzz import fuzz

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from comparison.catalogo_niveles import identificar_categoria_puesto  # noqa: E402
# Bono de confianza cuando ambos textos comparten el mismo "tipo de puesto"
# (Dirección, Subdirección, J.U.D., etc. según config.CATALOGO_NIVELES_POR_TIPO_PUESTO).
# Es intencionalmente modesto: el objetivo es ayudar a que títulos largos y
# compuestos ("Jefe de Departamento de Recursos Humanos" vs "... Recursos
# Humanos y Nómina") no se descarten solo por diluirse la similitud de texto
# en la parte descriptiva, SIN volver "válida" una coincidencia que ya era
# claramente distinta (los prefijos jerárquicos siguen penalizando aparte).
BONO_MISMA_CATEGORIA_PUESTO = 4.0
BONO_MISMA_CATEGORIA_SCORE_MINIMO = 60.0  # no aplica el bono a pares ya muy distintos


def coincidencia_exacta(original_a: str, original_b: str) -> bool:
    return original_a == original_b


def coincidencia_normalizada(norm_a: str, norm_b: str) -> bool:
    return norm_a == norm_b and norm_a != ""


def _modificadores_no_catalogados(texto_normalizado: str) -> set:
    """Modificadores genéricos de jerarquía que no son tipos oficiales del catálogo (ver config.py)."""
    encontrados = set()
    for modificador in config.MODIFICADORES_JERARQUICOS_NO_CATALOGADOS:
        if texto_normalizado.startswith(modificador + " ") or f" {modificador} " in f" {texto_normalizado} ":
            encontrados.add(modificador)
    return encontrados


_PATRON_SUFIJO_DISTINTIVO = re.compile(r"^[a-z]\d{0,2}$")


def _sufijo_distintivo(texto_normalizado: str):
    """
    Detecta un sufijo distintivo de una sola letra (con o sin número) al
    final del texto, ej. "...proyectos especiales a" -> "a", o
    "...obras publicas a1" -> "a1". Muy común en estructuras reales de
    gobierno para diferenciar oficinas idénticas en todo menos el sufijo
    (Dirección de Construcción "A"/"B"/"C"/"D", Subdirección "A1"/"A2"...).
    Regresa None si no hay un sufijo de este tipo.
    """
    if not texto_normalizado:
        return None
    ultima_palabra = texto_normalizado.split()[-1]
    return ultima_palabra if _PATRON_SUFIJO_DISTINTIVO.match(ultima_palabra) else None


def similitud_fuzzy(norm_a: str, norm_b: str) -> float:
    """Similitud 0-100 usando token_sort_ratio (tolera orden de palabras distinto)."""
    if not norm_a or not norm_b:
        return 0.0
    return fuzz.token_sort_ratio(norm_a, norm_b)


def evaluar_similitud_con_reglas(norm_a: str, norm_b: str) -> dict:
    """
    Combina similitud de texto con reglas de jerarquía para evitar falsos
    positivos como "director" vs "subdirector".

    Regresa:
      {
        "score": float (0-100, ya penalizado si aplica),
        "nivel": "exacta" | "normalizada" | "fuzzy_alta" | "revision" | "sin_coincidencia",
        "motivo": str
      }
    """
    if coincidencia_normalizada(norm_a, norm_b):
        return {"score": 100.0, "nivel": "normalizada", "motivo": "Coincidencia exacta tras normalización."}

    score_base = similitud_fuzzy(norm_a, norm_b)

    cat_a = identificar_categoria_puesto(norm_a)
    cat_b = identificar_categoria_puesto(norm_b)
    mods_a = _modificadores_no_catalogados(norm_a)
    mods_b = _modificadores_no_catalogados(norm_b)

    # Dos señales de conflicto DISTINTAS, que NO deben mezclarse:
    #   1. Ambos textos tienen un tipo de puesto RECONOCIDO en el catálogo
    #      y son DIFERENTES (ej. "dirección" vs "subdirección") -> conflicto
    #      claro, penaliza fuerte.
    #   2. Uno de los dos usa un modificador genérico no catalogado (vice-,
    #      encargado de-, etc.) que el otro no tiene -> también penaliza.
    # Importante: que UN SOLO lado tenga tipo reconocido y el otro no (por
    # ejemplo, un título incompleto o no estándar) NO cuenta como conflicto
    # — en ese caso no hay evidencia suficiente para penalizar, se deja que
    # la similitud de texto decida (cae en "revisión" si es ambiguo).
    conflicto_tipo = cat_a is not None and cat_b is not None and cat_a[0] != cat_b[0]
    conflicto_modificador = mods_a != mods_b

    sufijo_a = _sufijo_distintivo(norm_a)
    sufijo_b = _sufijo_distintivo(norm_b)
    conflicto_sufijo = sufijo_a is not None and sufijo_b is not None and sufijo_a != sufijo_b

    penalizacion = 0.0
    motivo = "Similitud de texto."
    if conflicto_tipo or conflicto_modificador or conflicto_sufijo:
        penalizacion = 25.0
        if conflicto_sufijo:
            detalle_conflicto = f"sufijos distintivos '{sufijo_a}' vs '{sufijo_b}' (ej. oficinas \"A\" vs \"B\")"
        elif conflicto_tipo:
            detalle_conflicto = f"tipos '{cat_a[0] if cat_a else '—'}' vs '{cat_b[0] if cat_b else '—'}'"
        else:
            detalle_conflicto = f"modificadores {mods_a or '{}'} vs {mods_b or '{}'}"
        motivo = f"Similitud de texto alta pero difieren en jerarquía ({detalle_conflicto}), posible puesto distinto."

    score_final = max(0.0, score_base - penalizacion)

    # Bono por compartir el mismo tipo de puesto (catálogo oficial, ya
    # canonizado: "jud" y "jefatura de unidad departamental" cuentan como
    # el mismo tipo), solo si la similitud base ya es razonable (evita
    # "rescatar" pares sin relación real).
    if score_final >= BONO_MISMA_CATEGORIA_SCORE_MINIMO and not conflicto_tipo and not conflicto_modificador and not conflicto_sufijo:
        if cat_a is not None and cat_b is not None and cat_a[0] == cat_b[0]:
            score_final = min(100.0, score_final + BONO_MISMA_CATEGORIA_PUESTO)
            motivo = f"{motivo} Ambos son de tipo '{cat_a[0]}' (bono de confianza aplicado)."

    if score_final >= config.FUZZY_UMBRAL_ALTA_CONFIANZA:
        nivel = "fuzzy_alta"
    elif score_final >= config.FUZZY_UMBRAL_REVISION_MIN:
        nivel = "revision"
    else:
        nivel = "sin_coincidencia"

    return {"score": round(score_final, 1), "nivel": nivel, "motivo": motivo}


def comparar_niveles(nivel_norm_a: str, nivel_norm_b: str) -> str:
    """
    Compara dos niveles ya normalizados (formato "N{numero}" o "" si no se
    pudo determinar). Regresa: "igual" | "distinto" | "falta_a" | "falta_b" | "ambos_faltan"
    """
    a_vacio = not nivel_norm_a
    b_vacio = not nivel_norm_b
    if a_vacio and b_vacio:
        return "ambos_faltan"
    if a_vacio:
        return "falta_a"
    if b_vacio:
        return "falta_b"
    return "igual" if nivel_norm_a == nivel_norm_b else "distinto"


def evaluar_coincidencia_por_componentes(clave_a: str, clave_b: str) -> dict:
    """
    Punto de entrada RECOMENDADO para comparar dos puestos (§17-19): si
    ambos comparten el mismo tipo de puesto según el catálogo oficial, la
    similitud se calcula ÚNICAMENTE sobre el nombre específico (la parte
    después del tipo) en vez de sobre el texto completo.

    Esto es importante porque comparar el texto completo cuando el tipo ya
    fue expandido (ej. "jud" -> "jefatura de unidad departamental") diluye
    artificialmente las diferencias reales: dos J.U.D. de áreas distintas
    comparten un prefijo largo idéntico, lo que infla el score de similitud
    de texto completo muy por encima de lo que refleja la diferencia real
    entre "Apoyo Administrativo" y "Administración", por ejemplo.

    Si los tipos no coinciden (o alguno no es reconocido por el catálogo),
    se compara el texto completo como respaldo (comportamiento anterior).
    """
    from comparison.catalogo_niveles import separar_tipo_y_nombre_especifico

    info_a = separar_tipo_y_nombre_especifico(clave_a)
    info_b = separar_tipo_y_nombre_especifico(clave_b)

    mismo_tipo_reconocido = (
        info_a["tipo_puesto"] is not None and info_a["tipo_puesto"] == info_b["tipo_puesto"]
    )
    if not mismo_tipo_reconocido:
        return evaluar_similitud_con_reglas(clave_a, clave_b)

    nombre_a, nombre_b = info_a["nombre_especifico"], info_b["nombre_especifico"]
    if not nombre_a and not nombre_b:
        # el puesto es literalmente solo el tipo, en ambos lados (ej. "Secretaría")
        return {"score": 100.0, "nivel": "normalizada", "motivo": "Mismo tipo de puesto, sin nombre específico adicional."}

    resultado = evaluar_similitud_con_reglas(nombre_a, nombre_b)
    resultado = dict(resultado)
    resultado["motivo"] = (
        f"Mismo tipo de puesto ('{info_a['tipo_puesto']}'); comparación por nombre específico "
        f"('{nombre_a}' vs '{nombre_b}'). {resultado['motivo']}"
    )
    return resultado
