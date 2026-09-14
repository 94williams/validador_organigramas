import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from normalization.normalizer import normalizar_puesto
from comparison.matcher import evaluar_similitud_con_reglas, comparar_niveles


def _sim(a, b):
    return evaluar_similitud_con_reglas(normalizar_puesto(a), normalizar_puesto(b))


def test_coincidencia_exacta_tras_normalizacion():
    r = _sim("SUBDIRECTOR DE RECURSOS HUMANOS", "SUBDIRECTOR DE RECURSOS HUMANOS ")
    assert r["nivel"] == "normalizada"
    assert r["score"] == 100.0


def test_director_vs_subdirector_no_debe_coincidir_automaticamente():
    r = _sim("DIRECTOR DE RECURSOS HUMANOS", "SUBDIRECTOR DE RECURSOS HUMANOS")
    assert r["nivel"] == "sin_coincidencia"


def test_diferencia_pequena_de_escritura_es_fuzzy_alta():
    r = _sim("Coordinador de Sistemas", "Coordinadora de Sistema")
    assert r["nivel"] in ("fuzzy_alta", "normalizada")


def test_diferencia_significativa_no_coincide():
    r = _sim("Director de Finanzas", "Auxiliar de Intendencia")
    assert r["nivel"] == "sin_coincidencia"


def test_comparar_niveles():
    assert comparar_niveles("N8", "N8") == "igual"
    assert comparar_niveles("N8", "N7") == "distinto"
    assert comparar_niveles("N8", "") == "falta_b"
    assert comparar_niveles("", "N8") == "falta_a"
    assert comparar_niveles("", "") == "ambos_faltan"
