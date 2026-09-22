import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from normalization.canonical_display import abreviar_puesto_canonico  # noqa: E402


def test_jud_completo_se_muestra_abreviado():
    assert (
        abreviar_puesto_canonico("Jefatura de Unidad Departamental de Recursos Humanos")
        == "J.U.D. de Recursos Humanos"
    )


def test_jud_ya_abreviado_se_estandariza_con_puntos():
    casos = [
        ("JUD de Recursos Humanos", "J.U.D. de Recursos Humanos"),
        ("J.U.D. de Control de Personal", "J.U.D. de Control de Personal"),
        ("JUD de Servicios Generales", "J.U.D. de Servicios Generales"),
        ("JUD de Soporte Técnico", "J.U.D. de Soporte Técnico"),
        ("JUD de TIC", "J.U.D. de TIC"),
    ]
    for entrada, esperado in casos:
        assert abreviar_puesto_canonico(entrada) == esperado


def test_lcp_completo_se_muestra_abreviado():
    assert (
        abreviar_puesto_canonico("Líder Coordinador de Proyectos de Planeación")
        == "L.C.P. de Planeación"
    )


def test_lcp_ya_abreviado_se_estandariza_con_puntos():
    casos = [
        ("LCP de Planeación", "L.C.P. de Planeación"),
        ("L.C.P. de Sistemas", "L.C.P. de Sistemas"),
        ("LCP de Administración", "L.C.P. de Administración"),
        ("LCP de TIC", "L.C.P. de TIC"),
    ]
    for entrada, esperado in casos:
        assert abreviar_puesto_canonico(entrada) == esperado


def test_otro_puesto_conserva_presentacion():
    assert (
        abreviar_puesto_canonico("Dirección General de Administración")
        == "Dirección General de Administración"
    )


def test_limpia_espacios_sin_modificar_contenido():
    assert (
        abreviar_puesto_canonico("  Dirección   General de   Administración  ")
        == "Dirección General de Administración"
    )
