"""
Pruebas de regresión para el diagnóstico de "falsos faltantes" (ver README,
sección de diagnóstico). Cada test aquí corresponde a una causa raíz
confirmada empíricamente antes de corregirla — si alguno de estos falla en
el futuro, significa que el bug correspondiente volvió a aparecer.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.models import PuestoRecord, Fuente, Ubicacion, TipoInconsistencia  # noqa: E402
from normalization.normalizer import normalizar_puesto, normalizar_nivel, normalizar_para_comparacion  # noqa: E402
from comparison.comparator import comparar_fuentes  # noqa: E402


def _rec(fuente, puesto, nivel, fila=1):
    return PuestoRecord(
        fuente=fuente, puesto_original=puesto, nivel_original=nivel,
        puesto_normalizado=normalizar_puesto(puesto),
        nivel_normalizado=normalizar_nivel(nivel) if nivel else None,
        ubicacion=Ubicacion(archivo="test", fila=fila),
    )


# ---------------------------------------------------------------------------
# CAUSA RAÍZ 1: asignación voraz por orden de procesamiento.
# Una clave de Excel con un sufijo (" A") se procesaba antes que la clave
# "base" y le robaba —vía fuzzy— la única coincidencia exacta disponible en
# Word, dejando la clave correcta como falso "Puesto faltante".
# ---------------------------------------------------------------------------
def test_no_roba_coincidencia_exacta_por_orden_de_procesamiento():
    # Nota: no se incluye Organigrama a propósito (queda vacío), por lo que
    # el tipo final de r_base será "Puesto faltante" (falta en Organigrama,
    # que en efecto no se proporcionó) — lo que se está probando aquí es
    # específicamente que el campo `word` se asigne a la clave correcta,
    # no el tipo de inconsistencia global.
    excel = [
        _rec(Fuente.EXCEL, "Subdirección de Obras Públicas A", "29", fila=2),
        _rec(Fuente.EXCEL, "Subdirección de Obras Públicas", "29", fila=3),
    ]
    word = [_rec(Fuente.WORD, "Subdirección de Obras Públicas", "29")]

    resultados = comparar_fuentes(excel, word, [])
    r_base = next(r for r in resultados if r.excel.puesto_original == "Subdirección de Obras Públicas")
    r_sufijo = next(r for r in resultados if r.excel.puesto_original == "Subdirección de Obras Públicas A")

    # la clave SIN sufijo debe llevarse la coincidencia exacta en Word
    assert r_base.word is not None
    assert r_base.word.puesto_original == "Subdirección de Obras Públicas"
    assert "Word" not in r_base.detalle  # no debe faltar en Word

    # la clave CON sufijo, al no existir en Word, debe quedar sin pareja ahí
    assert r_sufijo.word is None


def test_emparejamiento_global_no_depende_del_orden_de_insercion():
    # mismo caso que arriba pero con el orden de las claves de Excel invertido:
    # el resultado no debe cambiar (antes del fix, sí cambiaba).
    excel = [
        _rec(Fuente.EXCEL, "Subdirección de Obras Públicas", "29", fila=2),
        _rec(Fuente.EXCEL, "Subdirección de Obras Públicas A", "29", fila=3),
    ]
    word = [_rec(Fuente.WORD, "Subdirección de Obras Públicas", "29")]

    resultados = comparar_fuentes(excel, word, [])
    r_base = next(r for r in resultados if r.excel.puesto_original == "Subdirección de Obras Públicas")
    assert r_base.word is not None
    assert r_base.word.puesto_original == "Subdirección de Obras Públicas"


# ---------------------------------------------------------------------------
# CAUSA RAÍZ 2: abreviaturas no expandidas antes de comparar.
# "J.U.D." vs "Jefatura de Unidad Departamental" tenía una similitud de
# texto tan baja (~64%) que quedaba por debajo del umbral de revisión y se
# reportaba como faltante, aunque es exactamente el mismo puesto.
# ---------------------------------------------------------------------------
def test_abreviatura_jud_coincide_con_nombre_completo():
    excel = [_rec(Fuente.EXCEL, "J.U.D. de Limpieza Urbana Zona 1", "25")]
    word = [_rec(Fuente.WORD, "Jefatura de Unidad Departamental de Limpieza Urbana Zona 1", "25")]
    org = [_rec(Fuente.ORGANIGRAMA, "J.U.D. de Limpieza Urbana Zona 1", "25")]

    resultados = comparar_fuentes(excel, word, org)
    r = resultados[0]
    assert r.word is not None
    # Clasificación específica (más precisa que "normalización" genérica):
    # esta coincidencia dependió de reconocer J.U.D. como abreviatura.
    assert r.tipo_inconsistencia == TipoInconsistencia.COINCIDE_EQUIVALENCIA
    assert "J.U.D." in r.equivalencia_aplicada or "JUD" in r.equivalencia_aplicada


def test_abreviatura_lcp_coincide_con_nombre_completo():
    excel = [_rec(Fuente.EXCEL, "L.C.P. Zona Centro", "24")]
    word = [_rec(Fuente.WORD, "L.C.P. Zona Centro", "24")]
    org = [_rec(Fuente.ORGANIGRAMA, "Líder Coordinador de Proyectos Zona Centro", "24")]

    resultados = comparar_fuentes(excel, word, org)
    r = resultados[0]
    assert r.organigrama is not None
    assert r.tipo_inconsistencia == TipoInconsistencia.COINCIDE_EQUIVALENCIA
    assert "LCP" in r.equivalencia_aplicada


def test_normalizar_para_comparacion_expande_abreviaturas_conocidas():
    a = normalizar_para_comparacion(normalizar_puesto("J.U.D. de Recursos Humanos"))
    b = normalizar_para_comparacion(normalizar_puesto("Jefatura de Unidad Departamental de Recursos Humanos"))
    assert a == b


# ---------------------------------------------------------------------------
# Ejemplos textuales exactos proporcionados por el usuario, para verificar
# extremo a extremo (no solo a nivel de normalizador/matcher aislado).
# ---------------------------------------------------------------------------
def test_puesto_dividido_en_dos_lineas_coincide():
    # El salto de línea SÍ requiere normalizarse (no son bytes idénticos a
    # Word/Organigrama), así que el resultado esperado es "Coincide después
    # de normalización" -no "OK"-, que es justamente la clasificación
    # correcta para diferencias irrelevantes de formato (punto crítico:
    # NO debe ser "Puesto faltante").
    excel = [_rec(Fuente.EXCEL, "Jefe de\nDepartamento", "25")]
    word = [_rec(Fuente.WORD, "Jefe de Departamento", "25")]
    org = [_rec(Fuente.ORGANIGRAMA, "Jefe de Departamento", "25")]
    resultados = comparar_fuentes(excel, word, org)
    assert resultados[0].tipo_inconsistencia == TipoInconsistencia.COINCIDE_NORMALIZADO
    assert resultados[0].word is not None and resultados[0].organigrama is not None


def test_diferencia_menor_por_palabra_faltante_es_posible_coincidencia():
    excel = [_rec(Fuente.EXCEL, "Jefe de Departamento de Recursos Humanos", "25")]
    word = [_rec(Fuente.WORD, "Jefe de Departamento Recursos Humanos", "25")]  # falta la palabra "de"
    resultados = comparar_fuentes(excel, word, [])
    r = resultados[0]
    assert r.word is not None
    assert r.tipo_inconsistencia == TipoInconsistencia.POSIBLE_COINCIDENCIA
    assert r.confianza_match >= 93  # dentro de la banda de "alta confianza"


def test_faltante_real_sigue_siendo_faltante():
    # control negativo: un puesto que genuinamente no existe en ninguna otra
    # fuente debe seguir marcándose como faltante (el fix no debe "inventar"
    # coincidencias donde no las hay).
    excel = [_rec(Fuente.EXCEL, "Dirección de Innovación Tecnológica", "40")]
    word = [_rec(Fuente.WORD, "Subdirección de Comunicación Social", "29")]
    resultados = comparar_fuentes(excel, word, [])
    r = next(r for r in resultados if r.excel.puesto_original == "Dirección de Innovación Tecnológica")
    assert r.word is None
    assert r.tipo_inconsistencia == TipoInconsistencia.PUESTO_FALTANTE
