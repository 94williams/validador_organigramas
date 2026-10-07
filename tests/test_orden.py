from io import BytesIO
from pathlib import Path

import openpyxl
import pytest
from comparison.comparator import comparar_fuentes
from models.models import Fuente, PuestoRecord, TipoInconsistencia
from normalization.normalizer import normalizar_puesto
from reports.excel_report import generar_reporte_bytes


def registros(fuente, nombres):
    return [PuestoRecord(fuente, n, '25', normalizar_puesto(n), 'N25') for n in nombres]


A, B, C = 'Dirección de Finanzas', 'Subdirección de Archivo', 'JUD de Recursos Humanos'


@pytest.mark.parametrize('con_word', [True, False])
def test_orden_intercambiado_y_correccion(con_word):
    excel = registros(Fuente.EXCEL, [A, B, C])
    word = registros(Fuente.WORD, [A, B, C]) if con_word else []
    org = registros(Fuente.ORGANIGRAMA, [C, A, B])
    resultados = comparar_fuentes(excel, word, org, incluir_word=con_word)
    assert [r.excel.puesto_original for r in resultados] == [A, B, C]
    assert all(r.tipo_inconsistencia == TipoInconsistencia.ORDEN_DIFERENTE for r in resultados)
    assert resultados[0].posiciones['Excel'] == [1]
    assert resultados[0].posiciones['Organigrama'] == [2]
    assert 'esperada 1' in resultados[0].observacion_orden
    corregidos = comparar_fuentes(excel, word, registros(Fuente.ORGANIGRAMA, [A, B, C]), incluir_word=con_word)
    assert all(r.tipo_inconsistencia == TipoInconsistencia.OK for r in corregidos)
    assert all(r.estado_orden == 'Misma posición' for r in corregidos)


def test_word_y_organigrama_se_validan_independientemente():
    resultados = comparar_fuentes(registros(Fuente.EXCEL,[A,B,C]), registros(Fuente.WORD,[B,A,C]), registros(Fuente.ORGANIGRAMA,[A,C,B]))
    assert 'Word: posición 2' in resultados[0].observacion_orden
    assert 'Organigrama:' not in resultados[0].observacion_orden
    assert 'Organigrama: posición 2' in resultados[2].observacion_orden


def test_faltantes_desplazan_posiciones_y_se_conservan_niveles():
    excel = registros(Fuente.EXCEL, [A,B,C])
    org = registros(Fuente.ORGANIGRAMA, [B,C]); org[0].nivel_normalizado='N29'
    resultados = comparar_fuentes(excel, [], org, incluir_word=False)
    assert resultados[0].tipo_inconsistencia == TipoInconsistencia.PUESTO_FALTANTE
    assert resultados[1].tipo_inconsistencia == TipoInconsistencia.NIVEL_INCONSISTENTE
    assert resultados[1].estado_orden == 'Diferente posición'
    assert resultados[2].tipo_inconsistencia == TipoInconsistencia.ORDEN_DIFERENTE


def test_adicional_desplaza_los_demas():
    resultados = comparar_fuentes(registros(Fuente.EXCEL,[B,C]),[],registros(Fuente.ORGANIGRAMA,[A,B,C]),incluir_word=False)
    assert all(r.estado_orden == 'Diferente posición' for r in resultados[:2])
    assert resultados[-1].tipo_inconsistencia == TipoInconsistencia.PUESTO_ADICIONAL


def test_duplicados_no_se_certifican_como_misma_posicion():
    resultados = comparar_fuentes(registros(Fuente.EXCEL,[A,B]),[],registros(Fuente.ORGANIGRAMA,[A,B,A]),incluir_word=False)
    principal = next(r for r in resultados if r.excel and r.excel.puesto_original == A)
    assert principal.posiciones['Organigrama'] == [1,3]
    assert principal.estado_orden == 'No verificable'
    assert principal.tipo_inconsistencia == TipoInconsistencia.REQUIERE_REVISION


def test_error_extraccion_impide_certificar_orden():
    org = registros(Fuente.ORGANIGRAMA,[A]);org.insert(0,PuestoRecord(Fuente.ORGANIGRAMA,'',None,error='OCR'))
    resultado = comparar_fuentes(registros(Fuente.EXCEL,[A]),[],org,incluir_word=False)[-1]
    assert resultado.estado_orden == 'No verificable'
    assert resultado.tipo_inconsistencia == TipoInconsistencia.REQUIERE_REVISION


def test_equivalencia_fuera_de_posicion_y_exportacion():
    excel=registros(Fuente.EXCEL,[C,B])
    org=registros(Fuente.ORGANIGRAMA,[B,'Jefatura de Unidad Departamental de Recursos Humanos'])
    resultados=comparar_fuentes(excel,[],org,incluir_word=False)
    assert resultados[0].tipo_inconsistencia == TipoInconsistencia.ORDEN_DIFERENTE
    assert resultados[0].equivalencia_aplicada
    wb=openpyxl.load_workbook(BytesIO(generar_reporte_bytes(resultados,excel,[],org,modo='excel_organigrama')))
    headers=[c.value for c in wb['Detalle'][1]]
    assert 'Word - Posición' not in headers
    row=dict(zip(headers,[c.value for c in wb['Detalle'][2]]))
    assert row['Excel - Posición']=='1' and row['Organigrama - Posición']=='2'
    assert row['Resultado']=='Revisar'
    assert next(r[1] for r in wb['Resumen'].values if r[0]=='Puestos encontrados en diferente posición')==2


def test_organigrama_orden_visual_no_orden_de_dibujo(tmp_path):
    import fitz
    from extractors.organigrama_extractor import extraer_organigrama
    path=tmp_path/'org.pdf'
    doc=fitz.open();page=doc.new_page()
    for x,y,text in [(40,250,C),(300,40,B),(40,40,A)]:
        box=fitz.Rect(x,y,x+230,y+65)
        page.draw_rect(box)
        page.insert_textbox(fitz.Rect(x+5,y+5,x+225,y+60),text+'\n25',fontsize=10)
    doc.save(path);doc.close()
    records=extraer_organigrama(str(path))
    assert [r.puesto_original for r in records]==[A,B,C]

def test_ui_filtra_orden_incluso_con_nivel_inconsistente(monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setattr('config.APP_PASSWORD', None)
    excel=registros(Fuente.EXCEL,[A,B,C]); org=registros(Fuente.ORGANIGRAMA,[B,A,C])
    org[1].nivel_normalizado='N29'
    resultados=comparar_fuentes(excel,[],org,incluir_word=False)
    app=AppTest.from_file(str(Path(__file__).parents[1]/'ui/app.py'))
    from pipeline import ModoAnalisis
    app.session_state['resultado_analisis']=dict(resultados=resultados, excel_records=excel, word_records=[], organigrama_records=org, errores_fatales=[], modo=ModoAnalisis.EXCEL_ORGANIGRAMA)
    app.run(timeout=15)
    assert not app.exception
    assert next(m.value for m in app.metric if 'diferente posición' in m.label)=='2'
    app.checkbox[0].check().run(timeout=15)
    assert not app.exception
    assert len(app.dataframe[0].value)==2
    assert 'Nivel inconsistente' in app.dataframe[0].value['Tipo de inconsistencia'].tolist()
