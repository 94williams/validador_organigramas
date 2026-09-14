"""
Pruebas de la separación TIPO DE PUESTO + NOMBRE ESPECÍFICO y de la
clasificación formal de estado de nivel (válido / fuera de catálogo /
no encontrado / tipo no reconocido), según el prompt maestro de
refactorización.
"""
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.models import PuestoRecord, Fuente, Ubicacion, EstadoNivel  # noqa: E402
from normalization.normalizer import normalizar_puesto, normalizar_nivel  # noqa: E402
from comparison.catalogo_niveles import separar_tipo_y_nombre_especifico, enriquecer_con_catalogo  # noqa: E402


def _sep(puesto):
    return separar_tipo_y_nombre_especifico(normalizar_puesto(puesto))


# ---------------------------------------------------------------------------
# §47: separación tipo / nombre específico con los ejemplos exactos dados.
# ---------------------------------------------------------------------------
def test_jud_nombre_completo_abreviatura_con_puntos_y_sin_puntos_son_equivalentes():
    variantes = [
        "Jefatura de Unidad Departamental de Apoyo en Operación",
        "J.U.D. de Apoyo en Operación",
        "JUD de Apoyo en Operación",
    ]
    resultados = [_sep(v) for v in variantes]
    tipos = {r["tipo_puesto_display"] for r in resultados}
    nombres = {r["nombre_especifico"] for r in resultados}
    assert tipos == {"Jefatura de Unidad Departamental"}
    assert nombres == {"de apoyo en operacion"}
    assert all(r["niveles_catalogo"] == [27, 25] for r in resultados)


def test_lcp_nombre_completo_abreviatura_con_puntos_y_sin_puntos_son_equivalentes():
    variantes = [
        "Líder Coordinador de Proyectos de Ejecución y Apoyo Logístico",
        "L.C.P. de Ejecución y Apoyo Logístico",
        "LCP de Ejecución y Apoyo Logístico",
    ]
    resultados = [_sep(v) for v in variantes]
    tipos = {r["tipo_puesto_display"] for r in resultados}
    nombres = {r["nombre_especifico"] for r in resultados}
    assert tipos == {"Líder Coordinador de Proyectos"}
    assert nombres == {"de ejecucion y apoyo logistico"}
    assert all(r["niveles_catalogo"] == [24, 23] for r in resultados)


def test_direcciones_no_se_confunden_por_especificidad():
    casos = {
        "Dirección General de Atención y Gestión a la Demanda Ciudadana": "Dirección General",
        "Dirección Ejecutiva de Administración": "Dirección Ejecutiva",
        "Dirección de Seguimiento Interinstitucional": "Dirección",
        "Subdirección de Control de Indicadores": "Subdirección",
    }
    for puesto, tipo_esperado in casos.items():
        assert _sep(puesto)["tipo_puesto_display"] == tipo_esperado


# ---------------------------------------------------------------------------
# §18/§48: mismo tipo, nombre específico distinto -> NO deben tratarse
# como el mismo puesto.
# ---------------------------------------------------------------------------
def test_mismo_tipo_no_implica_mismo_puesto():
    a = _sep("JUD de Recursos Humanos")
    b = _sep("JUD de Recursos Materiales")
    assert a["tipo_puesto"] == b["tipo_puesto"]
    assert a["nombre_especifico"] != b["nombre_especifico"]


def test_direccion_general_no_se_confunde_con_direccion():
    a = _sep("Dirección General de Innovación")
    b = _sep("Dirección de Innovación")
    assert a["tipo_puesto"] != b["tipo_puesto"]


def test_lcp_areas_distintas_no_se_confunden():
    a = _sep("LCP de Planeación")
    b = _sep("LCP de Administración")
    assert a["tipo_puesto"] == b["tipo_puesto"]
    assert a["nombre_especifico"] != b["nombre_especifico"]


def test_sufijos_distintivos_a_b_no_se_confunden():
    # Hallazgo real: oficinas idénticas salvo por un sufijo distintivo
    # (muy común: Dirección de Construcción "A"/"B"/"C"/"D") se estaban
    # fusionando al 100% de confianza porque un solo carácter de
    # diferencia en un texto largo no baja lo suficiente el score de
    # fuzzy matching. Deben tratarse como oficinas distintas.
    from normalization.normalizer import normalizar_puesto
    from comparison.matcher import evaluar_similitud_con_reglas

    pares = [
        ("LCP de Proyectos Especiales A", "LCP de Proyectos Especiales B"),
        ("Subdirección de Construcción de Obras Públicas A1", "Subdirección de Construcción de Obras Públicas A2"),
        ("Dirección de Construcción de Obras Públicas A", "Dirección de Construcción de Obras Públicas B"),
    ]
    for a, b in pares:
        r = evaluar_similitud_con_reglas(normalizar_puesto(a), normalizar_puesto(b))
        assert r["nivel"] == "sin_coincidencia", f"{a!r} vs {b!r} -> {r}"


# ---------------------------------------------------------------------------
# §49: validación de nivel encontrado contra niveles del catálogo.
# ---------------------------------------------------------------------------
def _registro_enriquecido(puesto, nivel):
    r = PuestoRecord(
        fuente=Fuente.EXCEL, puesto_original=puesto, nivel_original=nivel,
        puesto_normalizado=normalizar_puesto(puesto),
        nivel_normalizado=normalizar_nivel(nivel) if nivel else None,
        ubicacion=Ubicacion(archivo="test"),
    )
    enriquecer_con_catalogo(r)
    return r


def test_jud_niveles_validos_e_invalido():
    assert _registro_enriquecido("JUD de Apoyo Operativo", "25").estado_nivel == EstadoNivel.VALIDO
    assert _registro_enriquecido("JUD de Apoyo Operativo", "27").estado_nivel == EstadoNivel.VALIDO
    assert _registro_enriquecido("JUD de Apoyo Operativo", "40").estado_nivel == EstadoNivel.FUERA_DE_CATALOGO


def test_lcp_niveles_validos_e_invalido():
    assert _registro_enriquecido("LCP de Planeación", "23").estado_nivel == EstadoNivel.VALIDO
    assert _registro_enriquecido("LCP de Planeación", "24").estado_nivel == EstadoNivel.VALIDO
    assert _registro_enriquecido("LCP de Planeación", "30").estado_nivel == EstadoNivel.FUERA_DE_CATALOGO


def test_direccion_general_niveles_validos_e_invalido():
    assert _registro_enriquecido("Dirección General de X", "45").estado_nivel == EstadoNivel.VALIDO
    assert _registro_enriquecido("Dirección General de X", "44").estado_nivel == EstadoNivel.VALIDO
    assert _registro_enriquecido("Dirección General de X", "40").estado_nivel == EstadoNivel.FUERA_DE_CATALOGO


# ---------------------------------------------------------------------------
# §22: nivel no encontrado NO debe asumirse, debe quedar explícito.
# ---------------------------------------------------------------------------
def test_nivel_no_encontrado_no_se_asume():
    r = _registro_enriquecido("Jefatura de Unidad Departamental de Apoyo", None)
    assert r.estado_nivel == EstadoNivel.NO_ENCONTRADO
    assert r.nivel_normalizado is None
    assert r.niveles_catalogo == [27, 25]  # el catálogo se conoce, pero el documento no trae nivel


def test_tipo_no_reconocido_no_valida_nivel():
    r = _registro_enriquecido("Asesor A", "43")
    assert r.tipo_puesto is None
    assert r.estado_nivel == EstadoNivel.TIPO_NO_RECONOCIDO
