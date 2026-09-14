"""
Prueba de regresión usando un organigrama real (Dictamen de Estructura
Orgánica, 7 páginas, cientos de puestos). Sirve para detectar si un cambio
futuro en el extractor rompe la detección de cajas vectoriales.

Los totales esperados por página vienen del campo "TOTAL DE PLAZAS" impreso
en cada página del propio documento. La página 2 tiene 65 plazas pero solo
62 cajas porque una caja agrupa "(4 PLAZAS) J.U.D. de Proyectos de Obras
Públicas A-D" como un solo rectángulo (comportamiento esperado, no un error).
"""
import os
import sys

import pytest

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractors.organigrama_extractor import extraer_organigrama  # noqa: E402

RUTA = os.path.join(os.path.dirname(__file__), "fixtures", "organigrama_real.pdf")

requiere_fixture = pytest.mark.skipif(not os.path.exists(RUTA), reason="Fixture real no disponible")

TOTALES_ESPERADOS_POR_PAGINA = {
    1: 27,
    2: 62,  # 65 plazas, pero 1 caja agrupa 4 plazas -> 62 cajas
    3: 32,
    4: 53,
    5: 37,
    6: 62,
    7: 11,
}


@requiere_fixture
def test_total_de_puestos_por_pagina():
    registros = extraer_organigrama(RUTA)
    conteo = {}
    for r in registros:
        pag = r.ubicacion.pagina
        conteo[pag] = conteo.get(pag, 0) + 1
    assert conteo == TOTALES_ESPERADOS_POR_PAGINA


@requiere_fixture
def test_todos_los_puestos_tienen_nivel():
    registros = extraer_organigrama(RUTA)
    sin_nivel = [r for r in registros if not r.nivel_original]
    assert sin_nivel == []


@requiere_fixture
def test_no_confunde_numeros_de_zona_con_el_nivel():
    # Caso real detectado: "J.U.D. de Limpieza Urbana Zona 1" / "Zona 2"
    # tienen nivel 25; el "1"/"2" es parte del nombre, no debe extraerse
    # como si fuera el nivel.
    registros = extraer_organigrama(RUTA)
    zonas = [
        r for r in registros
        if r.puesto_normalizado in ("jud de limpieza urbana zona 1", "jud de limpieza urbana zona 2")
    ]
    assert len(zonas) == 2
    for r in zonas:
        assert r.nivel_normalizado == "N25"


@requiere_fixture
def test_no_se_filtran_metadatos_como_puestos():
    registros = extraer_organigrama(RUTA)
    textos = [r.puesto_normalizado for r in registros]
    for palabra_prohibida in ("anexo", "oficio", "folio", "dictamen", "total de plazas"):
        assert not any(palabra_prohibida in t for t in textos), f"'{palabra_prohibida}' se coló como puesto"
