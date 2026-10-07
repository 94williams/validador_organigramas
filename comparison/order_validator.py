"""Verifica posiciones absolutas contra Excel sin alterar el emparejamiento."""
from collections import defaultdict

from models.models import TipoInconsistencia
from normalization.normalizer import normalizar_para_comparacion


def verificar_orden(resultados, excel, word, organigrama, incluir_word=True):
    fuentes = {"Excel": excel, "Organigrama": organigrama}
    if incluir_word:
        fuentes["Word"] = word
    indices = {}
    incompletas = set()
    for fuente, registros in fuentes.items():
        indice = defaultdict(list)
        for posicion, registro in enumerate((r for r in registros if r.valido), 1):
            indice[normalizar_para_comparacion(registro.puesto_normalizado)].append(posicion)
        indices[fuente] = indice
        if any(not r.valido for r in registros):
            incompletas.add(fuente)

    aprobados = {TipoInconsistencia.OK, TipoInconsistencia.COINCIDE_NORMALIZADO,
                 TipoInconsistencia.COINCIDE_EQUIVALENCIA}
    for resultado in resultados:
        registros = {"Excel": resultado.excel, "Organigrama": resultado.organigrama}
        if incluir_word:
            registros["Word"] = resultado.word
        resultado.posiciones = {
            fuente: indices[fuente].get(normalizar_para_comparacion(registro.puesto_normalizado), [])
            if registro is not None and registro.valido else []
            for fuente, registro in registros.items()
        }
        if resultado.excel is None or not resultado.excel.valido:
            resultado.estado_orden = "No verificable"
            resultado.observacion_orden = "Sin referencia válida en Excel."
            continue
        referencia = resultado.posiciones["Excel"]
        if len(referencia) != 1 or "Excel" in incompletas:
            resultado.estado_orden = "No verificable"
            resultado.observacion_orden = "Orden no verificable: duplicados o errores de extracción en Excel."
            if resultado.tipo_inconsistencia in aprobados:
                resultado.tipo_inconsistencia = TipoInconsistencia.REQUIERE_REVISION
            continue
        diferencias, pendientes = [], []
        for fuente in fuentes:
            if fuente == "Excel":
                continue
            posiciones = resultado.posiciones[fuente]
            if len(posiciones) != 1 or fuente in incompletas:
                pendientes.append(fuente)
            elif posiciones[0] != referencia[0]:
                diferencias.append(f"{fuente}: posición {posiciones[0]}; esperada {referencia[0]} según Excel")
        if diferencias:
            resultado.estado_orden = "Diferente posición"
            resultado.observacion_orden = (
                "Encontrado en diferente posición; realizar ajuste. " + "; ".join(diferencias) + "."
            )
            if resultado.tipo_inconsistencia in aprobados:
                resultado.tipo_inconsistencia = TipoInconsistencia.ORDEN_DIFERENTE
        else:
            resultado.estado_orden = "No verificable" if pendientes else "Misma posición"
            resultado.observacion_orden = "" if pendientes else "Misma posición en las fuentes analizadas."
        if pendientes:
            resultado.observacion_orden += (
                " Orden no verificable en: " + ", ".join(pendientes)
                + " (faltantes, duplicados o errores de extracción)."
            )
            if resultado.tipo_inconsistencia in aprobados:
                resultado.tipo_inconsistencia = TipoInconsistencia.REQUIERE_REVISION
