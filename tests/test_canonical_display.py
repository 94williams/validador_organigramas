import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from normalization.canonical_display import abreviar_puesto_canonico  # noqa: E402


def test_jud_completo_se_muestra_abreviado():
    assert (
        abreviar_puesto_canonico("Jefatura de Unidad Departamental de Recursos Humanos")
        == "J.U.D. de recursos humanos"
    )


def test_jud_ya_abreviado_se_estandariza_con_puntos():
    assert abreviar_puesto_canonico("JUD de Recursos Humanos") == "J.U.D. de recursos humanos"
    assert abreviar_puesto_canonico("J.U.D. de Recursos Humanos") == "J.U.D. de recursos humanos"


def test_lcp_completo_se_muestra_abreviado():
    assert (
        abreviar_puesto_canonico("Líder Coordinador de Proyectos de Planeación")
        == "L.C.P. de planeacion"
    )


def test_lcp_ya_abreviado_se_estandariza_con_puntos():
    assert abreviar_puesto_canonico("LCP de Planeación") == "L.C.P. de planeacion"
    assert abreviar_puesto_canonico("L.C.P. de Planeación") == "L.C.P. de planeacion"


def test_otro_puesto_no_se_abrevia():
    assert abreviar_puesto_canonico("Dirección General de Administración") == "direccion general de administracion"
