import os
import sys

import openpyxl

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from extractors.excel_extractor import extraer_excel  # noqa: E402


def test_excel_reconoce_denominacion_del_puesto(tmp_path):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Puestos"
    ws["A1"] = "CANTIDAD"
    ws["B1"] = "DENOMINACION DEL PUESTO"
    ws["C1"] = "NIVEL"
    ws["A2"] = "1"
    ws["B2"] = "Jefe de Departamento"
    ws["C2"] = 10

    ruta = tmp_path / "excel_puestos.xlsx"
    wb.save(ruta)

    registros = extraer_excel(str(ruta))

    assert len(registros) == 1
    assert registros[0].puesto_original == "Jefe de Departamento"
    assert registros[0].nivel_original == "10"
