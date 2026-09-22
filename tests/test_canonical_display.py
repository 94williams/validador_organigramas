import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from normalization.canonical_display import abreviar_puesto_canonico  # noqa: E402


def test_jud_completo_se_muestra_abreviado_y_legible():
    assert (
        abreviar_puesto_canonico("Jefatura de Unidad Departamental de Recursos Humanos")
        == "J.U.D. de Recursos Humanos"
    )


def test_jud_ya_abreviado_se_estandariza_con_puntos():
    assert abreviar_puesto_canonico("JUD de Recursos Humanos") == "J.U.D. de Recursos Humanos"
    assert abreviar_puesto_canonico("J.U.D. de Recursos Humanos") == "J.U.D. de Recursos Humanos"


def test_jud_en_mayusculas_se_formatea_para_reporte():
    assert abreviar_puesto_canonico("JEFATURA DE UNIDAD DEPARTAMENTAL DE RECURSOS HUMANOS") == "J.U.D. de Recursos Humanos"


def test_lcp_completo_se_muestra_abreviado_y_conserva_acento():
    assert (
        abreviar_puesto_canonico("Líder Coordinador de Proyectos de Planeación")
        == "L.C.P. de Planeación"
    )


def test_lcp_ya_abreviado_se_estandariza_con_puntos():
    assert abreviar_puesto_canonico("LCP de Planeación") == "L.C.P. de Planeación"
    assert abreviar_puesto_canonico("L.C.P. de Planeación") == "L.C.P. de Planeación"


def test_siglas_del_nombre_especifico_se_conservan():
    assert abreviar_puesto_canonico("JUD de TIC") == "J.U.D. de TIC"
    assert abreviar_puesto_canonico("LCP de TI") == "L.C.P. de TI"


def test_otro_puesto_conserva_texto_y_acentos():
    assert abreviar_puesto_canonico("Dirección General de Administración") == "Dirección General de Administración"


def test_solo_limpia_espacios_en_puesto_no_abreviado():
    assert abreviar_puesto_canonico("  Dirección   General de Administración  ") == "Dirección General de Administración"
