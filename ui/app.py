"""
Interfaz gráfica (Streamlit) de la herramienta de validación de organigramas.

Ejecutar con:
    streamlit run ui/app.py
    (o usar los scripts start_server.bat / start_server.sh para exponerla
    en la red local, ver README sección "Acceso local y remoto")

Flujo:
1. Elegir el modo de análisis: Completo (Excel+Word+Organigrama) o
   Excel vs Organigrama (Word queda oculto y no participa).
2. Cargar los archivos requeridos según el modo.
3. "Analizar documentos".
4. Ver resumen + tabla filtrable de inconsistencias.
5. Descargar el Excel de resultados.
"""
import os
import sys

import pandas as pd
import streamlit as st

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import ModoAnalisis  # noqa: E402
from models.models import TipoInconsistencia  # noqa: E402
from reports.excel_report import _fila_desde_resultado, _encabezados  # noqa: E402
from ui.analysis_service import analizar_archivos, contar_puestos  # noqa: E402
import config  # noqa: E402

st.set_page_config(page_title="Validador de Organigramas", layout="wide")


# ---------------------------------------------------------------------------
# Acceso protegido por contraseña (opcional). Se activa configurando
# config.APP_PASSWORD (ver README, sección de acceso remoto) — recomendado
# si la app va a exponerse fuera de tu máquina, aunque sea a través de una
# red privada tipo Tailscale.
# ---------------------------------------------------------------------------
def _acceso_permitido() -> bool:
    if not config.APP_PASSWORD:
        return True
    if st.session_state.get("autenticado"):
        return True
    st.title("🔒 Acceso al Validador de Organigramas")
    clave = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if clave == config.APP_PASSWORD:
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    return False


if not _acceso_permitido():
    st.stop()


st.title("📋 Validador de Puestos y Niveles")
st.caption(
    "Compara el Excel de referencia contra el Word y/o el organigrama de Visio (PDF) "
    "para detectar inconsistencias de puesto y nivel entre las fuentes."
)

if "resultado_analisis" not in st.session_state:
    st.session_state.resultado_analisis = None
if "reporte_bytes" not in st.session_state:
    st.session_state.reporte_bytes = None


with st.sidebar:
    st.header("1. Modo de análisis")
    etiqueta_modo = st.radio(
        "Tipo de análisis",
        ["Análisis completo (Excel + Word + Organigrama)", "Excel vs Organigrama (sin Word)"],
        help="En el segundo modo, Word queda completamente fuera del análisis: no se solicita, no se compara y no aparece en los resultados.",
    )
    modo = ModoAnalisis.COMPLETO if etiqueta_modo.startswith("Análisis completo") else ModoAnalisis.EXCEL_ORGANIGRAMA

    st.divider()
    st.header("2. Cargar archivos")
    archivo_excel = st.file_uploader("Excel de referencia", type=["xlsx", "xlsm"])
    hoja_excel = st.text_input(
        "Nombre de hoja (opcional)",
        help="Si se deja vacío, se buscan encabezados reconocibles en todas las hojas.",
    )
    archivo_organigrama = st.file_uploader("PDF del organigrama (Visio)", type=["pdf"])

    archivo_word = None
    if modo == ModoAnalisis.COMPLETO:
        archivo_word = st.file_uploader("Documento Word", type=["docx", "pdf"])

    st.divider()
    analizar = st.button("🔍 Analizar documentos", type="primary", use_container_width=True)

if analizar:
    archivos_requeridos = [archivo_excel, archivo_organigrama] + ([archivo_word] if modo == ModoAnalisis.COMPLETO else [])
    if not all(archivos_requeridos):
        faltan = "Excel, Organigrama" + (" y Word" if modo == ModoAnalisis.COMPLETO else "")
        st.error(f"Debes cargar: {faltan}.")
    else:
        st.session_state.resultado_analisis = None
        st.session_state.reporte_bytes = None
        with st.spinner("Extrayendo y comparando información..."):
            try:
                resultado, reporte = analizar_archivos(
                    archivo_excel, archivo_organigrama, archivo_word,
                    hoja_excel.strip() or None, modo,
                )
            except Exception as exc:
                st.error(f"No se pudo completar el análisis o generar el reporte: {exc}")
            else:
                st.session_state.resultado_analisis = resultado
                st.session_state.reporte_bytes = reporte

resultado = st.session_state.resultado_analisis

if resultado is None:
    st.info("Elige el modo de análisis, carga los archivos requeridos y presiona **Analizar documentos**.")
else:
    modo_actual = resultado.get("modo", ModoAnalisis.COMPLETO)
    incluye_word = modo_actual == ModoAnalisis.COMPLETO

    if resultado["errores_fatales"]:
        st.error("Análisis incompleto: los resultados pueden contener faltantes o adicionales derivados de errores de lectura.")
        for err in resultado["errores_fatales"]:
            st.write(f"- {err}")

    resultados = resultado["resultados"]

    st.header("2. Resumen")
    st.caption(f"Modo: {'Excel + Word + Organigrama' if incluye_word else 'Excel vs Organigrama (Word no participó)'}")

    fuentes = [("Excel", "excel_records"), ("Word", "word_records"), ("Organigrama", "organigrama_records")]
    if not incluye_word:
        fuentes = [f for f in fuentes if f[0] != "Word"]
    for columna, (nombre, clave) in zip(st.columns(len(fuentes)), fuentes):
        total, unicos = contar_puestos(resultado[clave])
        columna.metric(f"Puestos en {nombre}", total)
        columna.caption(f"{unicos} puestos únicos; {total} registros válidos.")

    ok_count = sum(1 for r in resultados if r.tipo_inconsistencia == TipoInconsistencia.OK)
    revisar_count = len(resultados) - ok_count
    col5, col6 = st.columns(2)
    col5.metric("✅ Sin problema", ok_count)
    col6.metric("⚠️ Requieren atención", revisar_count)

    st.metric("↕️ Encontrados en diferente posición", sum(
        r.estado_orden == "Diferente posición" for r in resultados
        if not r.puesto_clave_normalizada.startswith("[DUP-")))
    st.caption("Orden esperado: consecutivo de la columna I del Excel. Word: puestos leídos desde 1. "
               "Organigrama: cada rama completa, siguiendo conexiones; ramas hermanas de izquierda a derecha.")

    st.header("3. Detalle de inconsistencias")

    encabezados = _encabezados(modo_actual)
    filas = [_fila_desde_resultado(r, modo_actual) for r in resultados]
    df = pd.DataFrame(filas, columns=encabezados)

    tipos_disponibles = sorted(df["Tipo de inconsistencia"].unique())
    tipos_seleccionados = st.multiselect(
        "Filtrar por tipo de inconsistencia", tipos_disponibles, default=tipos_disponibles,
    )
    df_filtrado = df[df["Tipo de inconsistencia"].isin(tipos_seleccionados)]

    if st.checkbox("Solo puestos encontrados en diferente posición"):
        df_filtrado = df_filtrado[df_filtrado["Estado de orden"] == "Diferente posición"]

    busqueda = st.text_input("Buscar puesto")
    if busqueda:
        df_filtrado = df_filtrado[
            df_filtrado["Puesto (clave normalizada)"].str.contains(busqueda, case=False, na=False, regex=False)
        ]

    st.dataframe(df_filtrado, use_container_width=True, height=500)

    st.header("4. Exportar")
    if st.session_state.reporte_bytes is not None:
        st.download_button(
            "⬇️ Descargar Excel de resultados",
            data=st.session_state.reporte_bytes,
            file_name="reporte_inconsistencias.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
