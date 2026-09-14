"""
Punto de entrada por línea de comandos (alternativa a `streamlit run ui/app.py`).

Uso (análisis completo):
    python main.py --excel referencia.xlsx --organigrama organigrama.pdf \
                    --word documento.docx --salida reporte.xlsx [--hoja "Puestos"]

Uso (Excel vs Organigrama, sin Word):
    python main.py --modo excel_organigrama --excel referencia.xlsx \
                    --organigrama organigrama.pdf --salida reporte.xlsx
"""
import argparse
import sys

from pipeline import ejecutar_analisis, exportar_reporte, ModoAnalisis


def main():
    parser = argparse.ArgumentParser(
        description="Compara Excel, Word y/o Organigrama (PDF) y genera un reporte de inconsistencias."
    )
    parser.add_argument("--excel", required=True, help="Ruta al Excel de referencia (.xlsx)")
    parser.add_argument("--organigrama", required=True, help="Ruta al PDF del organigrama (Visio)")
    parser.add_argument(
        "--word", default=None,
        help="Ruta al documento Word (.docx o .pdf). Requerido solo en --modo completo.",
    )
    parser.add_argument(
        "--modo", choices=["completo", "excel_organigrama"], default="completo",
        help="'completo' = Excel+Word+Organigrama (por defecto). "
             "'excel_organigrama' = Excel vs Organigrama, Word no participa en absoluto.",
    )
    parser.add_argument("--salida", default="reporte_inconsistencias.xlsx", help="Ruta del Excel de resultados")
    parser.add_argument("--hoja", default=None, help="Nombre de hoja específica del Excel (opcional)")
    args = parser.parse_args()

    modo = ModoAnalisis.COMPLETO if args.modo == "completo" else ModoAnalisis.EXCEL_ORGANIGRAMA

    if modo == ModoAnalisis.COMPLETO and not args.word:
        parser.error("--word es obligatorio en --modo completo (o usa --modo excel_organigrama para omitir Word).")

    print(f"Analizando documentos (modo: {args.modo})...")
    resultado = ejecutar_analisis(
        ruta_excel=args.excel,
        ruta_organigrama_pdf=args.organigrama,
        ruta_word=args.word,
        hoja_excel=args.hoja,
        modo=modo,
    )

    if resultado["errores_fatales"]:
        print("\n⚠️  Se encontraron errores fatales en algunas fuentes:")
        for err in resultado["errores_fatales"]:
            print(f"  - {err}")

    total = len(resultado["resultados"])
    print(f"\nSe generaron {total} resultado(s) de comparación.")

    ruta_final = exportar_reporte(
        resultado["resultados"], args.salida,
        resultado["excel_records"], resultado["word_records"], resultado["organigrama_records"],
        modo=modo,
    )
    print(f"Reporte guardado en: {ruta_final}")

    return 0 if not resultado["errores_fatales"] else 1


if __name__ == "__main__":
    sys.exit(main())
