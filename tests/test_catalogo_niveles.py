import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from normalization.normalizer import normalizar_puesto, normalizar_nivel
from comparison.catalogo_niveles import validar_nivel_catalogo


def _validar(puesto, nivel):
    return validar_nivel_catalogo(normalizar_puesto(puesto), normalizar_nivel(nivel))


def test_nivel_correcto_para_secretaria():
    assert _validar("Secretaría de Obras y Servicios", "48") is None


def test_nivel_incorrecto_se_reporta():
    aviso = _validar("Secretaría de Obras y Servicios", "40")
    assert aviso is not None
    assert "N40" in aviso


def test_direccion_general_acepta_los_dos_niveles_oficiales():
    assert _validar("Dirección General de Construcción de Obras Públicas", "45") is None
    assert _validar("Dirección General de Construcción de Obras Públicas", "44") is None
    assert _validar("Dirección General de Construcción de Obras Públicas", "40") is not None


def test_excepcion_secretaria_particular_no_se_valida():
    # "Secretaría Particular" es nivel 44 en la realidad, no 48; al estar en
    # la lista de excepciones, no debe generar una advertencia aunque el
    # nivel no coincida con la categoría genérica "secretaria".
    assert _validar("Secretaría Particular", "44") is None


def test_abreviatura_jud_se_reconoce():
    assert _validar("J.U.D. de Limpieza Urbana Zona 1", "25") is None
    assert _validar("J.U.D. de Limpieza Urbana Zona 1", "10") is not None


def test_puesto_no_reconocido_no_genera_advertencia():
    assert _validar("Recepcionista", "1") is None


def test_sin_nivel_no_genera_advertencia():
    assert _validar("Secretaría de Obras y Servicios", None) is None
