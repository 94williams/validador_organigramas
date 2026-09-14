import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.models import PuestoRecord, Fuente, Ubicacion, TipoInconsistencia
from normalization.normalizer import normalizar_puesto, normalizar_nivel
from comparison.comparator import comparar_fuentes


def _rec(fuente, puesto, nivel, fila=1):
    return PuestoRecord(
        fuente=fuente,
        puesto_original=puesto,
        nivel_original=nivel,
        puesto_normalizado=normalizar_puesto(puesto),
        nivel_normalizado=normalizar_nivel(nivel) if nivel else None,
        ubicacion=Ubicacion(archivo="test", fila=fila),
    )


def test_caso_correcto_ok():
    excel = [_rec(Fuente.EXCEL, "Director de Área", "Nivel 8")]
    word = [_rec(Fuente.WORD, "Director de Área", "Nivel 8")]
    org = [_rec(Fuente.ORGANIGRAMA, "Director de Área", "Nivel 8")]
    resultados = comparar_fuentes(excel, word, org)
    assert any(r.tipo_inconsistencia == TipoInconsistencia.OK for r in resultados)


def test_diferencia_acento_y_mayusculas_coincide_normalizado():
    excel = [_rec(Fuente.EXCEL, "DIRECTOR DE AREA", "Nivel 8")]
    word = [_rec(Fuente.WORD, "Director de Área", "Nivel 8")]
    org = [_rec(Fuente.ORGANIGRAMA, "director de area", "Nivel 8")]
    resultados = comparar_fuentes(excel, word, org)
    assert any(r.tipo_inconsistencia == TipoInconsistencia.COINCIDE_NORMALIZADO for r in resultados)


def test_nivel_inconsistente():
    excel = [_rec(Fuente.EXCEL, "Jefe de Departamento", "Nivel 8")]
    word = [_rec(Fuente.WORD, "Jefe de Departamento", "Nivel 8")]
    org = [_rec(Fuente.ORGANIGRAMA, "Jefe de Departamento", "Nivel 7")]
    resultados = comparar_fuentes(excel, word, org)
    assert any(r.tipo_inconsistencia == TipoInconsistencia.NIVEL_INCONSISTENTE for r in resultados)


def test_puesto_faltante_en_organigrama():
    excel = [_rec(Fuente.EXCEL, "Jefe de Recursos Humanos", "Nivel 6")]
    word = [_rec(Fuente.WORD, "Jefe de Recursos Humanos", "Nivel 6")]
    org = []
    resultados = comparar_fuentes(excel, word, org)
    r = next(r for r in resultados if r.puesto_clave_normalizada == "jefe de recursos humanos")
    assert r.tipo_inconsistencia == TipoInconsistencia.PUESTO_FALTANTE
    assert "Organigrama" in r.detalle


def test_puesto_adicional_no_esta_en_excel():
    excel = []
    word = [_rec(Fuente.WORD, "Recepcionista", "Nivel 1")]
    org = [_rec(Fuente.ORGANIGRAMA, "Recepcionista", "Nivel 1")]
    resultados = comparar_fuentes(excel, word, org)
    assert any(r.tipo_inconsistencia == TipoInconsistencia.PUESTO_ADICIONAL for r in resultados)


def test_duplicado_mismo_nivel():
    excel = [
        _rec(Fuente.EXCEL, "Analista de Datos", "Nivel 4", fila=2),
        _rec(Fuente.EXCEL, "Analista de Datos", "Nivel 4", fila=3),
    ]
    resultados = comparar_fuentes(excel, [], [])
    duplicados = [r for r in resultados if r.tipo_inconsistencia == TipoInconsistencia.DUPLICADO]
    assert len(duplicados) == 2


def test_duplicado_con_nivel_distinto():
    excel = [
        _rec(Fuente.EXCEL, "Analista de Datos", "Nivel 4", fila=2),
        _rec(Fuente.EXCEL, "Analista de Datos", "Nivel 5", fila=3),
    ]
    resultados = comparar_fuentes(excel, [], [])
    assert any(r.tipo_inconsistencia == TipoInconsistencia.DUPLICADO_NIVEL_DISTINTO for r in resultados)


def test_coincidencia_aproximada_marca_posible_coincidencia():
    excel = [_rec(Fuente.EXCEL, "Coordinador de Sistemas", "Nivel 5")]
    word = [_rec(Fuente.WORD, "Coordinadora de Sistema", "Nivel 5")]
    resultados = comparar_fuentes(excel, word, [])
    assert any(
        r.tipo_inconsistencia in (TipoInconsistencia.POSIBLE_COINCIDENCIA, TipoInconsistencia.REQUIERE_REVISION)
        for r in resultados
    )


def test_director_no_se_confunde_con_subdirector():
    excel = [_rec(Fuente.EXCEL, "Director de Recursos Humanos", "Nivel 9")]
    word = [_rec(Fuente.WORD, "Subdirector de Recursos Humanos", "Nivel 7")]
    resultados = comparar_fuentes(excel, word, [])
    # deben aparecer como dos puestos distintos (faltante + adicional), NO como el mismo puesto
    tipos = {r.tipo_inconsistencia for r in resultados}
    assert TipoInconsistencia.PUESTO_FALTANTE in tipos or TipoInconsistencia.PUESTO_ADICIONAL in tipos
    assert TipoInconsistencia.OK not in tipos


def test_error_extraccion_no_detiene_el_resto():
    excel = [
        _rec(Fuente.EXCEL, "Jefe de Recursos Humanos", "Nivel 6"),
        PuestoRecord(fuente=Fuente.EXCEL, puesto_original="", nivel_original=None,
                     ubicacion=Ubicacion(archivo="x"), error="fila corrupta"),
    ]
    resultados = comparar_fuentes(excel, [], [])
    assert any(r.tipo_inconsistencia == TipoInconsistencia.ERROR_EXTRACCION for r in resultados)
    assert any(r.tipo_inconsistencia == TipoInconsistencia.PUESTO_FALTANTE for r in resultados)
