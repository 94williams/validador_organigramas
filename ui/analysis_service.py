"""Ejecuciones aisladas para la interfaz; los temporales duran solo el análisis."""
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline import ejecutar_analisis, ModoAnalisis
from reports.excel_report import generar_reporte_bytes


def contar_puestos(registros):
    validos = [r for r in registros if r.valido]
    return len(validos), len({r.puesto_normalizado for r in validos})


def analizar_archivos(excel, organigrama, word=None, hoja=None, modo=ModoAnalisis.COMPLETO):
    with TemporaryDirectory(prefix="validador_") as carpeta:
        def guardar(archivo, nombre):
            ruta = Path(carpeta) / (nombre + Path(archivo.name).suffix)
            ruta.write_bytes(archivo.getbuffer())
            return str(ruta)

        resultado = ejecutar_analisis(
            ruta_excel=guardar(excel, "excel"),
            ruta_organigrama_pdf=guardar(organigrama, "organigrama"),
            ruta_word=guardar(word, "word") if word is not None and modo == ModoAnalisis.COMPLETO else None,
            hoja_excel=hoja, modo=modo,
        )
        reporte = generar_reporte_bytes(
            resultado["resultados"], resultado["excel_records"], resultado["word_records"],
            resultado["organigrama_records"], modo=modo,
        )
        return resultado, reporte
