"""
Validación (informativa, no bloqueante) de si el nivel de un puesto
corresponde al catálogo oficial de niveles por tipo de puesto.

Esto es independiente de la comparación entre las 3 fuentes: aquí se valida
cada registro contra un catálogo externo de referencia (config.py), no entre
sí. Es útil para detectar, por ejemplo, errores de captura donde el nivel
no tiene ningún sentido para ese tipo de puesto.

Importante: varios tipos de puesto tienen títulos que "heredan" una palabra
de la jerarquía pero no corresponden a ese nivel (ej. "Secretaría
Particular" no es una Secretaría de nivel 48). Estos casos se excluyen vía
config.EXCEPCIONES_CATALOGO_NIVELES. Como el catálogo no puede cubrir todas
las excepciones posibles, este chequeo se reporta como ADVERTENCIA en una
columna aparte del reporte, nunca como un tipo de inconsistencia que
sobrescriba la comparación entre fuentes.
"""
import os
import re
import sys
from typing import Optional, Tuple

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

_CATEGORIAS_ORDENADAS = sorted(
    config.CATALOGO_NIVELES_POR_TIPO_PUESTO.items(), key=lambda kv: -len(kv[0])
)
_PATRON_NIVEL_NUM = re.compile(r"N(\d+)")


# Alias -> categoría canónica. Necesario porque el catálogo tiene entradas
# separadas para abreviatura y nombre completo (ej. "jud" y "jefatura de
# unidad departamental") con los MISMOS niveles pero como claves de texto
# distintas; sin canonizar, comparar "tipo_puesto" entre un registro que
# dice "JUD" y otro que dice "Jefatura de Unidad Departamental" fallaría
# por ser cadenas diferentes, aunque sean el mismo tipo (ver §10 del ajuste).
_ALIAS_CATEGORIA_CANONICA = {
    "jud": "jefatura de unidad departamental",
    "lcp": "lider coordinador de proyectos",
}


def identificar_categoria_puesto(puesto_normalizado: str) -> Optional[Tuple[str, list]]:
    """
    Identifica el "tipo de puesto" (Dirección, Subdirección, J.U.D., etc.)
    a partir de su texto normalizado, según config.CATALOGO_NIVELES_POR_TIPO_PUESTO.
    Regresa siempre la categoría CANÓNICA (ej. "jud" se resuelve a
    "jefatura de unidad departamental") para que dos registros del mismo
    tipo, sin importar si usan la abreviatura o el nombre completo, se
    puedan comparar por igualdad directa de tipo_puesto.
    Pública porque también la usa comparison/matcher.py para el bono de
    confianza por "mismo tipo de puesto" (ver evaluar_similitud_con_reglas).
    """
    if puesto_normalizado in config.EXCEPCIONES_CATALOGO_NIVELES:
        return None
    for categoria, niveles in _CATEGORIAS_ORDENADAS:
        if puesto_normalizado == categoria or puesto_normalizado.startswith(categoria + " "):
            categoria_canonica = _ALIAS_CATEGORIA_CANONICA.get(categoria, categoria)
            niveles_canonicos = config.CATALOGO_NIVELES_POR_TIPO_PUESTO[categoria_canonica]
            return categoria_canonica, niveles_canonicos
    return None


# Mapa de tipo canónico (clave normalizada -> "nombre de pila" oficial en
# forma legible, usado como tipo_puesto_display). Las abreviaturas
# (config.ABREVIATURAS_PUESTO) ya resuelven a su forma expandida ANTES de
# llegar aquí porque separar_tipo_y_nombre_especifico() normaliza primero
# para comparación (ver más abajo), así que "jud"/"lcp" no necesitan una
# entrada aparte: "jefatura de unidad departamental" y "lider coordinador
# de proyectos" ya cubren ambos casos.
_DISPLAY_TIPO = {
    "jefatura de gobierno": "Jefatura de Gobierno",
    "secretaria": "Secretaría",
    "subsecretaria": "Subsecretaría",
    "alcaldia": "Alcaldía",
    "coordinacion general": "Coordinación General",
    "direccion general": "Dirección General",
    "direccion ejecutiva": "Dirección Ejecutiva",
    "direccion tecnica": "Dirección Técnica",
    "direccion": "Dirección",
    "coordinacion": "Coordinación",
    "subdireccion tecnica": "Subdirección Técnica",
    "subdireccion": "Subdirección",
    "jefatura de unidad departamental": "Jefatura de Unidad Departamental",
    "jud": "Jefatura de Unidad Departamental",
    "lider coordinador de proyectos": "Líder Coordinador de Proyectos",
    "lcp": "Líder Coordinador de Proyectos",
    "enlace": "Enlace",
}


def separar_tipo_y_nombre_especifico(puesto_normalizado: str) -> dict:
    """
    Separa un puesto en:
      - tipo_puesto: clave canónica del catálogo (ej. "jefatura de unidad departamental")
      - tipo_puesto_display: forma legible (ej. "Jefatura de Unidad Departamental")
      - nombre_especifico: el resto del texto (ej. "de apoyo en operacion")
      - niveles_catalogo: niveles oficiales válidos para ese tipo

    Acepta el puesto_normalizado "crudo" (puede traer una abreviatura como
    "jud" o "lcp"); internamente lo expande primero con
    normalization.normalizer.normalizar_para_comparacion() para que el
    recorte de nombre_especifico sea consistente sin importar si el texto
    original usaba la abreviatura o el nombre completo.

    Regresa un dict con tipo_puesto=None si el texto no corresponde a
    ningún tipo del catálogo (puesto no clasificable, ej. "Asesor A").

    Esta es la ÚNICA función que debe usarse para esta separación — sustituye
    tanto a config.PREFIJOS_JERARQUICOS (lista ad-hoc de prefijos) como a
    cualquier lógica dispersa de "tipo de puesto" en otros módulos.
    """
    from normalization.normalizer import normalizar_para_comparacion  # import local: evita ciclo de imports

    texto_expandido = normalizar_para_comparacion(puesto_normalizado)
    resultado = identificar_categoria_puesto(texto_expandido)
    if resultado is None:
        return {
            "tipo_puesto": None, "tipo_puesto_display": None,
            "nombre_especifico": texto_expandido, "niveles_catalogo": [],
        }
    categoria, niveles = resultado
    nombre_especifico = texto_expandido[len(categoria):].strip()
    return {
        "tipo_puesto": categoria,
        "tipo_puesto_display": _DISPLAY_TIPO.get(categoria, categoria.title()),
        "nombre_especifico": nombre_especifico,
        "niveles_catalogo": niveles,
    }


# alias retrocompatible (uso interno de este módulo)
_identificar_categoria = identificar_categoria_puesto


def enriquecer_con_catalogo(registro) -> None:
    """
    Puebla en el propio PuestoRecord los campos derivados del catálogo:
    tipo_puesto, tipo_puesto_display, nombre_especifico, niveles_catalogo
    y estado_nivel. Se llama una vez por registro justo después de la
    extracción (ver pipeline.py), antes de la comparación entre fuentes.

    NO modifica puesto_original ni nivel_original — solo agrega
    información derivada para auditoría y para el matching por componentes.
    """
    from models.models import EstadoNivel  # import local: evita ciclo con models.py

    resultado = separar_tipo_y_nombre_especifico(registro.puesto_normalizado)
    registro.tipo_puesto = resultado["tipo_puesto"]
    registro.tipo_puesto_display = resultado["tipo_puesto_display"]
    registro.nombre_especifico = resultado["nombre_especifico"]
    registro.niveles_catalogo = resultado["niveles_catalogo"]

    if registro.tipo_puesto is None:
        registro.estado_nivel = EstadoNivel.TIPO_NO_RECONOCIDO
    elif not registro.nivel_normalizado:
        registro.estado_nivel = EstadoNivel.NO_ENCONTRADO
    else:
        m = re.fullmatch(r"N(\d+)", registro.nivel_normalizado)
        if m and int(m.group(1)) in resultado["niveles_catalogo"]:
            registro.estado_nivel = EstadoNivel.VALIDO
        else:
            registro.estado_nivel = EstadoNivel.FUERA_DE_CATALOGO


def validar_nivel_catalogo(puesto_normalizado: str, nivel_normalizado: Optional[str]) -> Optional[str]:
    """
    Regresa un mensaje de advertencia si el nivel no corresponde al
    catálogo oficial para ese tipo de puesto, o None si no aplica
    (tipo de puesto no reconocido, es una excepción conocida, o el
    nivel sí corresponde).
    """
    if not nivel_normalizado:
        return None  # ya se reporta como "nivel faltante" en la comparación

    resultado = _identificar_categoria(puesto_normalizado)
    if resultado is None:
        return None

    categoria, niveles_validos = resultado
    m = _PATRON_NIVEL_NUM.fullmatch(nivel_normalizado)
    if not m:
        return None

    nivel_num = int(m.group(1))
    if nivel_num not in niveles_validos:
        opciones = " o ".join(f"N{n}" for n in niveles_validos)
        return (
            f"Nivel {nivel_normalizado} no coincide con el catálogo esperado "
            f"para '{categoria}' (se esperaba {opciones})."
        )
    return None
