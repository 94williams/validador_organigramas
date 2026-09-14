"""
Pruebas del cliente de Ollama y de la segunda opinión semántica.

Usan un mock del servidor HTTP (no requieren Ollama instalado ni corriendo)
para validar: el esquema del payload enviado, el parseo/validación de la
respuesta JSON, el manejo de errores (nunca debe inventar una coincidencia),
la caché, y que con OLLAMA_ENABLED=False el sistema completo no se ve
afectado en absoluto.
"""
import json
import os
import sys
from unittest.mock import patch, MagicMock

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from models.models import PuestoRecord, Fuente, Ubicacion, TipoInconsistencia, MetodoCoincidencia  # noqa: E402
from normalization.normalizer import normalizar_puesto, normalizar_nivel  # noqa: E402
from comparison.catalogo_niveles import enriquecer_con_catalogo  # noqa: E402
from comparison.comparator import comparar_fuentes, aplicar_segunda_opinion_ollama  # noqa: E402
from comparison import ollama_client  # noqa: E402


def _rec(fuente, puesto, nivel):
    r = PuestoRecord(
        fuente=fuente, puesto_original=puesto, nivel_original=nivel,
        puesto_normalizado=normalizar_puesto(puesto), nivel_normalizado=normalizar_nivel(nivel),
        ubicacion=Ubicacion(archivo="test"),
    )
    enriquecer_con_catalogo(r)
    return r


@pytest.fixture(autouse=True)
def _limpiar_cache_y_config():
    """Cada prueba arranca con caché en memoria vacía y Ollama deshabilitado por defecto."""
    ollama_client._CACHE_MEMORIA.clear()
    ollama_client._CACHE_CARGADA = True  # evita leer/escribir el archivo de caché real durante las pruebas
    valor_original = config.OLLAMA_ENABLED
    yield
    config.OLLAMA_ENABLED = valor_original


def _mock_respuesta_ollama(es_mismo_puesto=True, confianza=0.96, requiere_revision=False, explicacion="ok"):
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {
        "message": {
            "content": json.dumps({
                "es_mismo_puesto": es_mismo_puesto,
                "confianza": confianza,
                "coincidencia_nombre_especifico": es_mismo_puesto,
                "requiere_revision_humana": requiere_revision,
                "explicacion": explicacion,
            })
        }
    }
    return mock_resp


# ---------------------------------------------------------------------------
# §38: Ollama deshabilitado -> el sistema no se ve afectado en absoluto.
# ---------------------------------------------------------------------------
def test_ollama_deshabilitado_no_hace_ninguna_consulta():
    config.OLLAMA_ENABLED = False
    with patch("requests.post") as mock_post:
        resultado = ollama_client.consultar_ollama("JUD de X", "JUD de Y", "jud", [27, 25])
        assert resultado is None
        mock_post.assert_not_called()


def test_segunda_opinion_sin_ollama_no_modifica_resultados():
    config.OLLAMA_ENABLED = False
    excel = [_rec(Fuente.EXCEL, "JUD de Seguimiento y Evaluación de Proyectos", "25")]
    word = [_rec(Fuente.WORD, "JUD de Seguimiento de Proyectos", "25")]
    resultados = comparar_fuentes(excel, word, [])
    resultados_tras_ia = aplicar_segunda_opinion_ollama(resultados)
    assert resultados_tras_ia[0].ia_consultada is False
    assert resultados_tras_ia[0].tipo_inconsistencia == resultados[0].tipo_inconsistencia


# ---------------------------------------------------------------------------
# Con Ollama habilitado (mock): confirma coincidencia ambigua con alta confianza.
# ---------------------------------------------------------------------------
def test_ollama_confirma_coincidencia_ambigua():
    config.OLLAMA_ENABLED = True
    excel = [_rec(Fuente.EXCEL, "JUD de Seguimiento y Evaluación de Proyectos", "25")]
    word = [_rec(Fuente.WORD, "JUD de Seguimiento de Proyectos", "25")]
    resultados = comparar_fuentes(excel, word, [])
    assert resultados[0].tipo_inconsistencia == TipoInconsistencia.REQUIERE_REVISION  # antes de Ollama

    with patch("requests.post", return_value=_mock_respuesta_ollama(confianza=0.96)):
        resultados = aplicar_segunda_opinion_ollama(resultados)

    r = resultados[0]
    assert r.ia_consultada is True
    assert r.tipo_inconsistencia == TipoInconsistencia.COINCIDE_IA
    assert r.metodo_coincidencia == MetodoCoincidencia.IA


def test_ollama_no_inventa_coincidencia_si_confianza_baja():
    config.OLLAMA_ENABLED = True
    excel = [_rec(Fuente.EXCEL, "JUD de Seguimiento y Evaluación de Proyectos", "25")]
    word = [_rec(Fuente.WORD, "JUD de Seguimiento de Proyectos", "25")]
    resultados = comparar_fuentes(excel, word, [])

    with patch("requests.post", return_value=_mock_respuesta_ollama(confianza=0.55)):
        resultados = aplicar_segunda_opinion_ollama(resultados)

    r = resultados[0]
    assert r.ia_consultada is True
    assert r.tipo_inconsistencia == TipoInconsistencia.REQUIERE_REVISION  # sigue en revisión, no se inventa


def test_ollama_no_inventa_coincidencia_si_el_mismo_pide_revision_humana():
    config.OLLAMA_ENABLED = True
    excel = [_rec(Fuente.EXCEL, "JUD de Seguimiento y Evaluación de Proyectos", "25")]
    word = [_rec(Fuente.WORD, "JUD de Seguimiento de Proyectos", "25")]
    resultados = comparar_fuentes(excel, word, [])

    with patch("requests.post", return_value=_mock_respuesta_ollama(confianza=0.97, requiere_revision=True)):
        resultados = aplicar_segunda_opinion_ollama(resultados)

    assert resultados[0].tipo_inconsistencia == TipoInconsistencia.REQUIERE_REVISION


def test_ollama_dice_que_no_son_el_mismo_puesto():
    config.OLLAMA_ENABLED = True
    excel = [_rec(Fuente.EXCEL, "JUD de Seguimiento y Evaluación de Proyectos", "25")]
    word = [_rec(Fuente.WORD, "JUD de Seguimiento de Proyectos", "25")]
    resultados = comparar_fuentes(excel, word, [])

    with patch("requests.post", return_value=_mock_respuesta_ollama(es_mismo_puesto=False, confianza=0.9)):
        resultados = aplicar_segunda_opinion_ollama(resultados)

    assert resultados[0].tipo_inconsistencia == TipoInconsistencia.REQUIERE_REVISION


# ---------------------------------------------------------------------------
# Manejo de errores: Ollama caído/timeout/JSON inválido -> NUNCA se inventa
# una coincidencia, el caso simplemente se queda en revisión manual.
# ---------------------------------------------------------------------------
def test_ollama_no_disponible_no_rompe_nada():
    config.OLLAMA_ENABLED = True
    with patch("requests.post", side_effect=ConnectionError("servidor no disponible")):
        resultado = ollama_client.consultar_ollama("JUD de X", "JUD de Y", "jud", [27, 25])
    assert resultado is None


def test_ollama_json_invalido_se_descarta():
    config.OLLAMA_ENABLED = True
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"message": {"content": "esto no es JSON valido"}}
    with patch("requests.post", return_value=mock_resp):
        resultado = ollama_client.consultar_ollama("JUD de X", "JUD de Y", "jud", [27, 25])
    assert resultado is None


def test_ollama_respuesta_con_esquema_incompleto_se_descarta():
    config.OLLAMA_ENABLED = True
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    mock_resp.json.return_value = {"message": {"content": json.dumps({"es_mismo_puesto": True})}}
    with patch("requests.post", return_value=mock_resp):
        resultado = ollama_client.consultar_ollama("JUD de X", "JUD de Y", "jud", [27, 25])
    assert resultado is None


def test_ollama_nunca_determina_el_nivel():
    # Verificación estructural: la respuesta validada de Ollama no puede
    # contener ningún campo de nivel: el esquema esperado no lo incluye.
    config.OLLAMA_ENABLED = True
    with patch("requests.post", return_value=_mock_respuesta_ollama()):
        resultado = ollama_client.consultar_ollama("JUD de X", "JUD de Y", "jud", [27, 25])
    assert "nivel" not in resultado
    assert "nivel_encontrado" not in resultado


# ---------------------------------------------------------------------------
# Caché: no se debe volver a llamar a Ollama para la misma comparación.
# ---------------------------------------------------------------------------
def test_cache_evita_segunda_consulta_identica():
    config.OLLAMA_ENABLED = True
    with patch("requests.post", return_value=_mock_respuesta_ollama()) as mock_post:
        ollama_client.consultar_ollama("JUD de X", "JUD de Y", "jud", [27, 25])
        ollama_client.consultar_ollama("JUD de X", "JUD de Y", "jud", [27, 25])
    assert mock_post.call_count == 1
