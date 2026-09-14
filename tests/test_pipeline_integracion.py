"""
Prueba de integración end-to-end usando los archivos de ejemplo generados
en tests/fixtures/ (Excel, Word .docx, PDF de organigrama).

Si los fixtures no existen (por ejemplo, en un entorno limpio sin
LibreOffice/reportlab para regenerarlos), la prueba se salta en vez de fallar.
"""
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import ejecutar_analisis  # noqa: E402
from models.models import TipoInconsistencia  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
RUTA_EXCEL = os.path.join(FIXTURES, "referencia.xlsx")
RUTA_ORG = os.path.join(FIXTURES, "organigrama.pdf")
RUTA_WORD = os.path.join(FIXTURES, "documento_word.docx")

requiere_fixtures = pytest.mark.skipif(
    not (os.path.exists(RUTA_EXCEL) and os.path.exists(RUTA_ORG) and os.path.exists(RUTA_WORD)),
    reason="Fixtures de ejemplo no generados",
)


@requiere_fixtures
def test_pipeline_completo_sin_errores_fatales():
    resultado = ejecutar_analisis(RUTA_EXCEL, RUTA_ORG, RUTA_WORD)
    assert resultado["errores_fatales"] == []
    assert len(resultado["resultados"]) > 0


@requiere_fixtures
def test_pipeline_detecta_tipos_esperados():
    resultado = ejecutar_analisis(RUTA_EXCEL, RUTA_ORG, RUTA_WORD)
    tipos_encontrados = {r.tipo_inconsistencia for r in resultado["resultados"]}
    esperados = {
        TipoInconsistencia.DUPLICADO,
        TipoInconsistencia.COINCIDE_NORMALIZADO,
        TipoInconsistencia.NIVEL_INCONSISTENTE,
        TipoInconsistencia.PUESTO_FALTANTE,
        TipoInconsistencia.PUESTO_ADICIONAL,
    }
    assert esperados.issubset(tipos_encontrados)
