"""
Pruebas de regresión para los bugs de extracción de Word diagnosticados en
la revisión integral: encabezado "DENOMINACIÓN" solo (sin "DEL PUESTO"),
tablas sin bordes visibles en PDF, columna CANTIDAD, y tablas que continúan
entre páginas sin repetir encabezado.
"""
import os
import sys

import docx
import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractors.word_extractor import (  # noqa: E402
    _encontrar_indices_columnas,
    _extraer_por_patron_de_linea,
    extraer_word,
)


# ---------------------------------------------------------------------------
# BUG 1: "DENOMINACIÓN" sola (sin "DEL PUESTO") no se reconocía como
# columna de puesto -> la tabla completa se descartaba en silencio.
# ---------------------------------------------------------------------------
def test_encabezado_denominacion_sola_se_reconoce():
    idx_puesto, idx_nivel, idx_cantidad = _encontrar_indices_columnas(
        ["CANTIDAD", "DENOMINACIÓN", "NIVEL"]
    )
    assert idx_puesto == 1
    assert idx_nivel == 2
    assert idx_cantidad == 0


def test_tabla_docx_con_encabezado_denominacion_sola(tmp_path):
    doc = docx.Document()
    tabla = doc.add_table(rows=1, cols=3)
    hdr = tabla.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "CANTIDAD", "DENOMINACIÓN", "NIVEL"
    fila = tabla.add_row().cells
    fila[0].text, fila[1].text, fila[2].text = "1", "Jefatura de Gobierno de la Ciudad de México", "49"

    ruta = tmp_path / "prueba.docx"
    doc.save(str(ruta))

    registros = extraer_word(str(ruta))
    assert len(registros) == 1
    assert registros[0].puesto_original == "Jefatura de Gobierno de la Ciudad de México"
    assert registros[0].nivel_original == "49"
    assert registros[0].cantidad == "1"


# ---------------------------------------------------------------------------
# BUG 2: columna CANTIDAD debe conservarse como información adicional.
# ---------------------------------------------------------------------------
def test_columna_cantidad_se_conserva(tmp_path):
    doc = docx.Document()
    tabla = doc.add_table(rows=1, cols=3)
    hdr = tabla.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "CANTIDAD", "DENOMINACIÓN DEL PUESTO", "NIVEL"
    datos = [
        ("1", "Jefatura de Gobierno de la Ciudad de México", "49"),
        ("1", "Secretaría Técnica de la Jefatura de Gobierno", "46"),
        ("1", "Subdirección de Seguimiento de Acuerdos", "29"),
        ("1", "Coordinación de Apoyo Técnico", "44"),
        ("1", "Secretaría Particular", "48"),
        ("1", "Dirección de Organización y Logística Institucional", "40"),
    ]
    for c, p, n in datos:
        fila = tabla.add_row().cells
        fila[0].text, fila[1].text, fila[2].text = c, p, n

    ruta = tmp_path / "prueba.docx"
    doc.save(str(ruta))

    registros = extraer_word(str(ruta))
    assert len(registros) == 6  # y no "Word: 1"
    assert all(r.cantidad == "1" for r in registros)


# ---------------------------------------------------------------------------
# BUG 3: tablas sin bordes visibles en PDF (pdfplumber no detecta ninguna
# tabla) deben recuperarse vía el respaldo de patrón de línea.
# ---------------------------------------------------------------------------
def _requiere_libreoffice():
    import shutil
    return shutil.which("soffice") is None or shutil.which("libreoffice") is None


@pytest.mark.skipif(_requiere_libreoffice(), reason="LibreOffice no disponible para generar el PDF de prueba")
def test_tabla_sin_bordes_se_recupera_con_patron_de_linea(tmp_path):
    import subprocess

    doc = docx.Document()
    doc.add_heading("Estructura de Puestos", level=1)
    tabla = doc.add_table(rows=1, cols=3)
    hdr = tabla.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "CANTIDAD", "DENOMINACIÓN DEL PUESTO", "NIVEL"
    for i in range(1, 16):
        fila = tabla.add_row().cells
        fila[0].text = "1"
        fila[1].text = f"Puesto de prueba numero {i}"
        fila[2].text = str(20 + (i % 10))

    ruta_docx = tmp_path / "tabla_sin_bordes.docx"
    doc.save(str(ruta_docx))

    subprocess.run(
        ["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(tmp_path), str(ruta_docx)],
        check=True, capture_output=True, timeout=60,
    )
    ruta_pdf = tmp_path / "tabla_sin_bordes.pdf"
    assert ruta_pdf.exists()

    registros = extraer_word(str(ruta_pdf))
    assert len(registros) == 15
    assert all(r.nivel_original for r in registros)
    # se generaron por el respaldo de patrón de línea -> confianza reducida
    assert all(r.confianza_extraccion < 1.0 for r in registros)


def test_fila_pdf_envuelta_conserva_nombre_completo():
    texto = (
        '1 Jefatura de Unidad Departamental de Seguimiento y Control de Información Contable\n'
        'y Financiera "A" 25\n'
    )

    registros = _extraer_por_patron_de_linea(texto, "prueba.pdf", 1)

    assert len(registros) == 1
    assert registros[0].puesto_original == (
        'Jefatura de Unidad Departamental de Seguimiento y Control de Información Contable '
        'y Financiera "A"'
    )
    assert registros[0].nivel_original == "25"


# ---------------------------------------------------------------------------
# Falsos puestos: encabezados repetidos u otras filas administrativas no
# deben convertirse en registros.
# ---------------------------------------------------------------------------
def test_fila_de_encabezado_repetida_no_se_cuenta_como_puesto(tmp_path):
    doc = docx.Document()
    tabla = doc.add_table(rows=1, cols=3)
    hdr = tabla.rows[0].cells
    hdr[0].text, hdr[1].text, hdr[2].text = "CANTIDAD", "DENOMINACIÓN DEL PUESTO", "NIVEL"
    filas_datos = [
        ("1", "Jefatura de Gobierno de la Ciudad de México", "49"),
        ("", "CANTIDAD", ""),  # fila de encabezado repetida por error de captura
        ("1", "Secretaría Particular", "48"),
    ]
    for c, p, n in filas_datos:
        fila = tabla.add_row().cells
        fila[0].text, fila[1].text, fila[2].text = c, p, n

    ruta = tmp_path / "prueba.docx"
    doc.save(str(ruta))

    registros = extraer_word(str(ruta))
    assert len(registros) == 2
    assert all("CANTIDAD" not in r.puesto_original for r in registros)
