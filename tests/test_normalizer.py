import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from normalization.normalizer import normalizar_puesto, normalizar_nivel, es_nivel_valido


def test_acentos_y_mayusculas():
    assert normalizar_puesto("DIRECTOR DE ÁREA") == normalizar_puesto("Director de Area")


def test_espacios_duplicados_y_tabs():
    assert normalizar_puesto("JEFE  DE  DEPARTAMENTO") == normalizar_puesto("JEFE DE DEPARTAMENTO")
    assert normalizar_puesto("Jefe\tde\nDepartamento") == "jefe de departamento"


def test_comillas_y_guiones():
    assert normalizar_puesto('"Director" - General') == normalizar_puesto("Director-General")
    assert normalizar_puesto("Director \u2013 General") == normalizar_puesto("Director-General")


def test_espacios_inicio_fin():
    assert normalizar_puesto("  Analista de Datos  ") == "analista de datos"


def test_normalizar_nivel_representaciones_equivalentes():
    equivalentes = ["8", "Nivel 8", "NIVEL 8", "N-8", "Nvl. 8", 8, 8.0]
    normalizados = {normalizar_nivel(v) for v in equivalentes}
    assert normalizados == {"N8"}


def test_normalizar_nivel_vacio_o_invalido():
    assert normalizar_nivel(None) == ""
    assert normalizar_nivel("") == ""
    assert normalizar_nivel("sin nivel asignado") == ""


def test_es_nivel_valido():
    assert es_nivel_valido("N8") is True
    assert es_nivel_valido("") is False
    assert es_nivel_valido("nivel8") is False
