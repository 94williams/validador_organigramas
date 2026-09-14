"""
Pruebas de los casos obligatorios del catálogo de equivalencias
institucionales (L.C.P., J.U.D., etc.) y de la advertencia para
abreviaturas con forma reconocible pero no registradas en el catálogo.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.models import PuestoRecord, Fuente, Ubicacion, TipoInconsistencia  # noqa: E402
from normalization.normalizer import (  # noqa: E402
    normalizar_puesto, normalizar_nivel, normalizar_para_comparacion,
    detectar_posible_abreviatura_no_reconocida,
)
from comparison.comparator import comparar_fuentes  # noqa: E402


def _rec(fuente, puesto, nivel=None):
    return PuestoRecord(
        fuente=fuente, puesto_original=puesto, nivel_original=nivel,
        puesto_normalizado=normalizar_puesto(puesto),
        nivel_normalizado=normalizar_nivel(nivel) if nivel else None,
        ubicacion=Ubicacion(archivo="test"),
    )


# ---------------------------------------------------------------------------
# Casos obligatorios 1-5 del documento de equivalencias institucionales
# ---------------------------------------------------------------------------
def test_caso1_lcp_tres_fuentes_coincide():
    excel = [_rec(Fuente.EXCEL, "Líder Coordinador de Proyectos", "24")]
    word = [_rec(Fuente.WORD, "L.C.P.", "24")]
    org = [_rec(Fuente.ORGANIGRAMA, "LCP", "24")]
    r = comparar_fuentes(excel, word, org)[0]
    assert r.word is not None and r.organigrama is not None
    assert r.tipo_inconsistencia == TipoInconsistencia.COINCIDE_EQUIVALENCIA


def test_caso2_jud_tres_fuentes_coincide():
    excel = [_rec(Fuente.EXCEL, "Jefatura de Unidad Departamental", "25")]
    word = [_rec(Fuente.WORD, "J.U.D.", "25")]
    org = [_rec(Fuente.ORGANIGRAMA, "JUD", "25")]
    r = comparar_fuentes(excel, word, org)[0]
    assert r.word is not None and r.organigrama is not None
    assert r.tipo_inconsistencia == TipoInconsistencia.COINCIDE_EQUIVALENCIA


def test_caso3_jud_compuesto_no_se_marca_faltante():
    excel = [_rec(Fuente.EXCEL, "Jefatura de Unidad Departamental de Recursos Humanos", "25")]
    word = [_rec(Fuente.WORD, "J.U.D. de Recursos Humanos", "25")]
    org = [_rec(Fuente.ORGANIGRAMA, "JUD Recursos Humanos", "25")]
    r = comparar_fuentes(excel, word, org)[0]
    # No debe ser faltante bajo ninguna circunstancia (el punto crítico del
    # diagnóstico); puede quedar como coincidencia por equivalencia o como
    # posible coincidencia de alta confianza si además falta una preposición.
    assert r.tipo_inconsistencia != TipoInconsistencia.PUESTO_FALTANTE
    assert r.word is not None and r.organigrama is not None


def test_caso4_puesto_realmente_distinto_no_coincide():
    excel = [_rec(Fuente.EXCEL, "Jefatura de Unidad Departamental", "25")]
    org = [_rec(Fuente.ORGANIGRAMA, "Subdirección", "29")]
    r = comparar_fuentes(excel, [], org)[0]
    assert r.organigrama is None
    assert r.tipo_inconsistencia == TipoInconsistencia.PUESTO_FALTANTE


def test_caso5_similar_no_equivalente_requiere_revision():
    excel = [_rec(Fuente.EXCEL, "Líder Coordinador de Proyectos", "24")]
    org = [_rec(Fuente.ORGANIGRAMA, "Coordinador de Proyectos", "24")]
    r = comparar_fuentes(excel, [], org)[0]
    # NO debe asumirse automáticamente que son iguales
    assert r.tipo_inconsistencia != TipoInconsistencia.OK
    assert r.tipo_inconsistencia != TipoInconsistencia.COINCIDE_EQUIVALENCIA
    assert r.tipo_inconsistencia == TipoInconsistencia.REQUIERE_REVISION


# ---------------------------------------------------------------------------
# La equivalencia debe ser bidireccional: no importa en qué fuente aparezca
# la abreviatura (a diferencia de lo típico, donde solo el organigrama abrevia).
# ---------------------------------------------------------------------------
def test_equivalencia_es_bidireccional():
    excel = [_rec(Fuente.EXCEL, "L.C.P.", "24")]
    word = [_rec(Fuente.WORD, "Líder Coordinador de Proyectos", "24")]
    org = [_rec(Fuente.ORGANIGRAMA, "LCP", "24")]
    r = comparar_fuentes(excel, word, org)[0]
    assert r.word is not None and r.organigrama is not None
    assert r.tipo_inconsistencia == TipoInconsistencia.COINCIDE_EQUIVALENCIA


# ---------------------------------------------------------------------------
# No inventar equivalencias no confirmadas.
# ---------------------------------------------------------------------------
def test_abreviatura_desconocida_se_marca_como_advertencia_no_como_error():
    aviso = detectar_posible_abreviatura_no_reconocida("C.P.A. de Finanzas")
    assert aviso is not None
    assert "C.P.A." in aviso


def test_abreviatura_conocida_no_genera_advertencia():
    assert detectar_posible_abreviatura_no_reconocida("J.U.D. de Recursos Humanos") is None


def test_puesto_sin_abreviatura_no_genera_advertencia():
    assert detectar_posible_abreviatura_no_reconocida("Director de Finanzas") is None


def test_abreviatura_no_reconocida_no_se_expande_ni_se_inventa_significado():
    # el texto normalizado de una abreviatura NO catalogada se deja tal cual,
    # no se le asigna un significado arbitrario.
    normalizado = normalizar_puesto("C.P.A. de Finanzas")
    comparacion = normalizar_para_comparacion(normalizado)
    assert comparacion == normalizado  # sin cambios, porque "cpa" no está en el catálogo


# ---------------------------------------------------------------------------
# Auditoría: la nota de equivalencia aplicada debe quedar registrada.
# ---------------------------------------------------------------------------
def test_nota_de_equivalencia_aplicada_queda_registrada():
    excel = [_rec(Fuente.EXCEL, "Líder Coordinador de Proyectos", "24")]
    word = [_rec(Fuente.WORD, "L.C.P.", "24")]
    r = comparar_fuentes(excel, word, [])[0]
    assert "LCP" in r.equivalencia_aplicada
    assert "lider coordinador de proyectos" in r.equivalencia_aplicada
