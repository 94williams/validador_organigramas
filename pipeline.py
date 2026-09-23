"""
Pipeline de orquestación: conecta extractores -> comparador -> reporte.
Es el punto de entrada que usa tanto la interfaz (ui/app.py) como los tests.

Cada etapa está envuelta en try/except: un error en una fuente NO detiene
el procesamiento de las otras (ver punto 16 del planteamiento original).

MODOS DE ANÁLISIS: la extracción, normalización, catálogo y comparación son
EXACTAMENTE la misma lógica para cualquier combinación de fuentes — lo único
que cambia entre modos es qué fuentes se extraen y se pasan al comparador.
Esto permite agregar modos futuros (ej. "Word vs Organigrama") sin duplicar
ninguna lógica: basta con decidir qué extractores llamar.
"""
import os
import traceback
from enum import Enum
from typing import List, Optional

from extractors.excel_extractor import extraer_excel
from extractors.word_extractor import extraer_word
from extractors.organigrama_extractor import extraer_organigrama
from comparison.comparator import comparar_fuentes, aplicar_segunda_opinion_ollama
from comparison.catalogo_niveles import enriquecer_con_catalogo
from reports.excel_report import generar_reporte
from models.models import PuestoRecord, Fuente, Ubicacion
from utils.logger import get_logger

logger = get_logger("pipeline")


class ModoAnalisis(str, Enum):
    COMPLETO = "completo"                  # Excel + Word + Organigrama
    EXCEL_ORGANIGRAMA = "excel_organigrama"  # Excel + Organigrama (Word no participa)


def _registro_error_fatal(fuente: Fuente, archivo: str, mensaje: str) -> PuestoRecord:
    return PuestoRecord(
        fuente=fuente, puesto_original="", nivel_original=None,
        ubicacion=Ubicacion(archivo=os.path.basename(archivo) if archivo else "N/D"),
        error=mensaje,
    )


def ejecutar_analisis(
    ruta_excel: str,
    ruta_organigrama_pdf: str,
    ruta_word: Optional[str] = None,
    hoja_excel: Optional[str] = None,
    modo: ModoAnalisis = ModoAnalisis.COMPLETO,
) -> dict:
    """
    Ejecuta el pipeline completo. Regresa un dict con:
      - excel_records, word_records, organigrama_records (listas de PuestoRecord;
        word_records queda como [] si modo=EXCEL_ORGANIGRAMA o no se dio ruta_word)
      - resultados (lista de ComparisonResult)
      - errores_fatales (lista de strings, etapas que fallaron por completo)
      - modo (el modo efectivamente usado)

    En modo EXCEL_ORGANIGRAMA, Word no se extrae en absoluto (ni siquiera si
    se proporciona ruta_word por error) — el análisis es exclusivamente
    Excel vs Organigrama, tal como en modo COMPLETO pero sin la tercera fuente.
    """
    errores_fatales: List[str] = []
    usar_word = modo == ModoAnalisis.COMPLETO

    try:
        excel_records = extraer_excel(ruta_excel, hoja=hoja_excel)
    except Exception as e:
        logger.error(f"Fallo fatal extrayendo Excel: {e}\n{traceback.format_exc()}")
        errores_fatales.append(f"Excel: {e}")
        excel_records = [_registro_error_fatal(Fuente.EXCEL, ruta_excel, str(e))]

    if usar_word:
        try:
            word_records = extraer_word(ruta_word)
        except Exception as e:
            logger.error(f"Fallo fatal extrayendo Word: {e}\n{traceback.format_exc()}")
            errores_fatales.append(f"Word: {e}")
            word_records = [_registro_error_fatal(Fuente.WORD, ruta_word, str(e))]
    else:
        word_records = []  # Word no participa en este modo (§4, §8 del pedido)

    try:
        organigrama_records = extraer_organigrama(ruta_organigrama_pdf)
    except Exception as e:
        logger.error(f"Fallo fatal extrayendo organigrama: {e}\n{traceback.format_exc()}")
        errores_fatales.append(f"Organigrama: {e}")
        organigrama_records = [_registro_error_fatal(Fuente.ORGANIGRAMA, ruta_organigrama_pdf, str(e))]

    # Enriquecer cada registro con tipo de puesto / nombre específico /
    # estado de nivel según el catálogo oficial (config.py), ANTES de
    # comparar entre fuentes. No modifica el texto original.
    for lista in (excel_records, word_records, organigrama_records):
        for r in lista:
            if r.valido:
                enriquecer_con_catalogo(r)

    try:
        resultados = comparar_fuentes(excel_records, word_records, organigrama_records, incluir_word=usar_word)
        resultados = aplicar_segunda_opinion_ollama(resultados)
    except Exception as e:
        logger.error(f"Fallo fatal en la comparación: {e}\n{traceback.format_exc()}")
        errores_fatales.append(f"Comparación: {e}")
        resultados = []

    return {
        "excel_records": excel_records,
        "word_records": word_records,
        "organigrama_records": organigrama_records,
        "resultados": resultados,
        "errores_fatales": errores_fatales,
        "modo": modo,
    }


def exportar_reporte(resultados, ruta_salida: str, excel_records=None, word_records=None,
                      organigrama_records=None, modo: ModoAnalisis = ModoAnalisis.COMPLETO) -> str:
    return generar_reporte(resultados, ruta_salida, excel_records, word_records, organigrama_records, modo)
