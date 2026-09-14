"""
Pruebas de la interfaz Streamlit usando streamlit.testing.v1.AppTest
(renderiza la app en memoria, sin necesidad de un servidor real).
"""
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

pytest.importorskip("streamlit.testing.v1")
from streamlit.testing.v1 import AppTest  # noqa: E402

RUTA_APP = os.path.join(os.path.dirname(__file__), "..", "ui", "app.py")


@pytest.fixture(autouse=True)
def _limpiar_env():
    valor_previo = os.environ.pop("VALIDADOR_PASSWORD", None)
    # config.py lee VALIDADOR_PASSWORD solo al importarse (correcto para el
    # proceso real, donde la variable de entorno se fija antes de arrancar).
    # En las pruebas, varias corridas de AppTest comparten el mismo proceso
    # de Python, así que hay que forzar una re-importación para que cada
    # prueba vea el valor de entorno que le corresponde.
    sys.modules.pop("config", None)
    yield
    sys.modules.pop("config", None)
    if valor_previo is not None:
        os.environ["VALIDADOR_PASSWORD"] = valor_previo
    else:
        os.environ.pop("VALIDADOR_PASSWORD", None)


def test_sin_password_configurado_muestra_la_app_directamente():
    os.environ.pop("VALIDADOR_PASSWORD", None)
    at = AppTest.from_file(RUTA_APP)
    at.run(timeout=15)
    assert at.exception == []
    titulos = [t.value for t in at.title]
    assert any("Validador de Puestos" in t for t in titulos)


def test_con_password_configurado_bloquea_el_acceso():
    os.environ["VALIDADOR_PASSWORD"] = "clave-segura-de-prueba"
    at = AppTest.from_file(RUTA_APP)
    at.run(timeout=15)
    assert at.exception == []
    titulos = [t.value for t in at.title]
    assert any("Acceso al Validador" in t for t in titulos)
    assert len(at.radio) == 0
    assert len(at.text_input) == 1


def test_selector_de_modo_presente_sin_password():
    os.environ.pop("VALIDADOR_PASSWORD", None)
    at = AppTest.from_file(RUTA_APP)
    at.run(timeout=15)
    assert at.exception == []
    assert len(at.radio) == 1
    opciones = at.radio[0].options
    assert any("completo" in o.lower() for o in opciones)
    assert any("sin word" in o.lower() or "organigrama" in o.lower() for o in opciones)
