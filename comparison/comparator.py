"""
Comparador de 3 fuentes (Excel = referencia principal, Word, Organigrama).

Algoritmo de emparejamiento (revisado — ver diagnóstico de falsos "faltante"):
1. Se agrupan los registros válidos de cada fuente por su puesto_normalizado
   (esto agrupa automáticamente los duplicados exactos dentro de una misma
   fuente) y, por separado, por una CLAVE DE COMPARACIÓN con abreviaturas
   expandidas (config.ABREVIATURAS_PUESTO / normalizador.normalizar_para_comparacion),
   que es la que realmente se usa para emparejar entre fuentes distintas.
2. El emparejamiento entre Excel y cada una de Word/Organigrama se resuelve
   de forma GLOBAL: se generan TODOS los pares candidatos posibles (exactos
   y aproximados) con su puntuación, se ordenan de mayor a menor puntuación,
   y se asignan de forma voraz en ese orden global — NO en el orden en que
   aparecen las claves de Excel. Esto evita que una coincidencia aproximada
   "robe" la pareja de otra clave que tenía una coincidencia exacta
   disponible (bug diagnosticado: causaba falsos "puesto faltante").
3. Las claves de Word/Organigrama que no encontraron pareja en Excel se
   evalúan entre sí con el mismo algoritmo global y se reportan como
   "Puesto adicional".
4. Se compara el nivel de cada tripleta encontrada.
5. Los registros con error de extracción generan su propio resultado.
"""
import os
import sys
from collections import defaultdict
from typing import Dict, List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from models.models import (  # noqa: E402
    PuestoRecord, ComparisonResult, TipoInconsistencia, NivelComparacion, Fuente, MetodoCoincidencia,
)
from comparison.matcher import evaluar_similitud_con_reglas, evaluar_coincidencia_por_componentes, comparar_niveles  # noqa: E402
from comparison.catalogo_niveles import validar_nivel_catalogo  # noqa: E402
from comparison.ollama_client import consultar_ollama  # noqa: E402
from normalization.normalizer import normalizar_para_comparacion, detectar_abreviaturas_en_texto, detectar_posible_abreviatura_no_reconocida  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger("comparator")


def _agrupar_por_normalizado(records: List[PuestoRecord]) -> Dict[str, List[PuestoRecord]]:
    grupos: Dict[str, List[PuestoRecord]] = defaultdict(list)
    for r in records:
        grupos[r.puesto_normalizado].append(r)
    return dict(grupos)


def _agrupar_por_clave_comparacion(records: List[PuestoRecord]) -> Dict[str, List[PuestoRecord]]:
    """
    Igual que _agrupar_por_normalizado, pero con abreviaturas expandidas.
    Esta es la agrupación que se usa para EMPAREJAR entre fuentes distintas
    (Excel<->Word, Excel<->Organigrama); _agrupar_por_normalizado se sigue
    usando tal cual para detectar duplicados DENTRO de una misma fuente.
    """
    grupos: Dict[str, List[PuestoRecord]] = defaultdict(list)
    for r in records:
        grupos[normalizar_para_comparacion(r.puesto_normalizado)].append(r)
    return dict(grupos)


def _nota_equivalencia_aplicada(rec_a: PuestoRecord, rec_b: PuestoRecord) -> str:
    """
    Si la coincidencia entre dos registros dependió de expandir una
    abreviatura institucional (J.U.D., L.C.P., etc.), regresa una nota
    de auditoría como "J.U.D. → jefatura de unidad departamental".
    Regresa "" si no hubo ninguna abreviatura involucrada.
    """
    abrevs = set(detectar_abreviaturas_en_texto(rec_a.puesto_normalizado))
    abrevs |= set(detectar_abreviaturas_en_texto(rec_b.puesto_normalizado))
    if not abrevs:
        return ""
    notas = [f"{a.upper()} → {config.ABREVIATURAS_PUESTO[a]}" for a in sorted(abrevs)]
    return "Equivalencia aplicada: " + "; ".join(notas)


def _emparejar_conjunto(claves_origen: List[str], grupos_destino: Dict[str, list]) -> Dict[str, dict]:
    """
    Empareja cada clave de `claves_origen` con la mejor clave disponible en
    `grupos_destino`, de forma GLOBAL (no voraz por orden de iteración):

    1. Genera todos los pares candidatos (clave_origen, clave_destino) con
       su puntuación: 100 si son idénticas, o el score de fuzzy+reglas si
       supera el umbral de revisión.
    2. Ordena TODOS los candidatos (de cualquier origen) por puntuación
       descendente.
    3. Asigna en ese orden: la primera vez que una clave de origen o de
       destino aparece en un candidato, se consolida esa asignación y
       ambas claves quedan "usadas" para el resto de candidatos.

    Esto garantiza que una coincidencia exacta (100) siempre se asigne antes
    que cualquier coincidencia aproximada, sin importar en qué orden estén
    las claves de origen — que era la causa del bug de falsos "faltante".

    Regresa: {clave_origen: {"clave_destino":..., "score":..., "nivel":..., "motivo":...}}
    """
    candidatos = []
    claves_destino = list(grupos_destino.keys())

    for clave_o in claves_origen:
        if clave_o in grupos_destino:
            candidatos.append({
                "origen": clave_o, "destino": clave_o, "score": 100.0,
                "nivel": "exacta_o_normalizada", "motivo": "",
            })
        else:
            for clave_d in claves_destino:
                resultado = evaluar_coincidencia_por_componentes(clave_o, clave_d)
                if resultado["nivel"] in ("fuzzy_alta", "revision"):
                    candidatos.append({
                        "origen": clave_o, "destino": clave_d, "score": resultado["score"],
                        "nivel": resultado["nivel"], "motivo": resultado["motivo"],
                    })

    # Las coincidencias exactas/normalizadas SIEMPRE se asignan antes que
    # cualquier coincidencia aproximada, sin importar el puntaje numérico.
    # (El bono por "mismo tipo de puesto" en matcher.py puede empujar un
    # score fuzzy hasta empatar con 100; sin esta prioridad explícita, un
    # empate podía hacer que la coincidencia aproximada "ganara" por orden
    # de aparición, robándole la pareja exacta a la clave correcta.)
    candidatos.sort(key=lambda c: (c["nivel"] == "exacta_o_normalizada", c["score"]), reverse=True)

    asignaciones: Dict[str, dict] = {}
    usados_destino = set()
    for cand in candidatos:
        if cand["origen"] in asignaciones or cand["destino"] in usados_destino:
            continue
        asignaciones[cand["origen"]] = cand
        usados_destino.add(cand["destino"])

    return asignaciones


def _resultado_desde_error(record: PuestoRecord) -> ComparisonResult:
    r = ComparisonResult(puesto_clave_normalizada="[ERROR]")
    campo = {
        Fuente.EXCEL: "excel", Fuente.WORD: "word", Fuente.ORGANIGRAMA: "organigrama",
    }[record.fuente]
    setattr(r, campo, record)
    r.tipo_inconsistencia = TipoInconsistencia.ERROR_EXTRACCION
    r.detalle = record.error or "Error de extracción no especificado."
    return r


def _metodo_desde_nivel_comparacion(nivel: NivelComparacion) -> MetodoCoincidencia:
    """Traduce el nivel de comparación de nombre (matching) al método de
    coincidencia legible para auditoría (§41 del prompt maestro)."""
    return {
        NivelComparacion.EXACTA: MetodoCoincidencia.EXACTA,
        NivelComparacion.NORMALIZADA: MetodoCoincidencia.NORMALIZACION,
        NivelComparacion.EQUIVALENCIA_INSTITUCIONAL: MetodoCoincidencia.EQUIVALENCIA_INSTITUCIONAL,
        NivelComparacion.FUZZY_ALTA: MetodoCoincidencia.FUZZY,
        NivelComparacion.FUZZY_REVISION: MetodoCoincidencia.REVISION_MANUAL,
        NivelComparacion.SIN_COINCIDENCIA: MetodoCoincidencia.NO_APLICA,
    }.get(nivel, MetodoCoincidencia.NO_APLICA)


def _construir_resultado(
    clave: str,
    excel_rec: Optional[PuestoRecord],
    word_rec: Optional[PuestoRecord],
    org_rec: Optional[PuestoRecord],
    nivel_comp_nombre: NivelComparacion,
    confianza: float,
    detalle_match: str = "",
    incluir_word: bool = True,
) -> ComparisonResult:
    resultado = ComparisonResult(
        puesto_clave_normalizada=clave,
        excel=excel_rec, word=word_rec, organigrama=org_rec,
        nivel_comparacion_nombre=nivel_comp_nombre,
        confianza_match=confianza,
        metodo_coincidencia=_metodo_desde_nivel_comparacion(nivel_comp_nombre),
    )

    # Si Word no participa en este modo de análisis (ver pipeline.ModoAnalisis),
    # se excluye por completo de "fuentes presentes" y de "faltantes": no
    # tiene sentido reportar "falta en Word" cuando Word nunca se analizó.
    fuentes_relevantes = [excel_rec, org_rec] + ([word_rec] if incluir_word else [])
    fuentes_presentes = [f for f in fuentes_relevantes if f is not None]
    faltantes = []
    if excel_rec is None:
        faltantes.append("Excel")
    if incluir_word and word_rec is None:
        faltantes.append("Word")
    if org_rec is None:
        faltantes.append("Organigrama")
    nota_faltantes = f" (No se encontró en: {', '.join(faltantes)}.)" if faltantes else ""

    # --- PRECEDENCIA DE CLASIFICACIÓN ---
    # 1) Ambigüedad de nombre entre fuentes (fuzzy) es lo más urgente de
    #    revisar, independientemente de si además falta en alguna fuente.
    # 2) Si el nombre coincide con certeza (exacta/normalizada) pero falta
    #    en alguna fuente, se clasifica como faltante/adicional.
    # 3) Si está presente en todas con nombre coincidente, se evalúa el nivel.
    if nivel_comp_nombre == NivelComparacion.FUZZY_REVISION:
        resultado.tipo_inconsistencia = TipoInconsistencia.REQUIERE_REVISION
        resultado.detalle = (detalle_match or "Similitud de nombre no concluyente entre fuentes.") + nota_faltantes

    elif nivel_comp_nombre == NivelComparacion.FUZZY_ALTA:
        resultado.tipo_inconsistencia = TipoInconsistencia.POSIBLE_COINCIDENCIA
        resultado.detalle = (detalle_match or "Coincidencia de nombre por similitud alta (no exacta).") + nota_faltantes

    elif faltantes:
        if excel_rec is None:
            resultado.tipo_inconsistencia = TipoInconsistencia.PUESTO_ADICIONAL
            resultado.detalle = (
                f"Puesto no encontrado en Excel (fuente de referencia). "
                f"Presente en: {', '.join(f.fuente.value for f in fuentes_presentes)}."
            )
        else:
            resultado.tipo_inconsistencia = TipoInconsistencia.PUESTO_FALTANTE
            resultado.detalle = f"Falta en: {', '.join(faltantes)}."

    else:
        resultado.tipo_inconsistencia = TipoInconsistencia.OK
        resultado.detalle = "Presente en todas las fuentes analizadas."

    # --- Comparar niveles si hay al menos 2 fuentes con el puesto presente
    #     y la clasificación de nombre no fue una ambigüedad no resuelta ---
    if len(fuentes_presentes) >= 2 and resultado.tipo_inconsistencia not in (
        TipoInconsistencia.REQUIERE_REVISION, TipoInconsistencia.POSIBLE_COINCIDENCIA,
    ):
        niveles_normalizados = {f.fuente.value: f.nivel_normalizado for f in fuentes_presentes}
        valores_unicos = set(v for v in niveles_normalizados.values() if v)
        hay_vacios = any(not v for v in niveles_normalizados.values())

        if len(valores_unicos) > 1:
            resultado.tipo_inconsistencia = TipoInconsistencia.NIVEL_INCONSISTENTE
            detalle_niveles = ", ".join(f"{k}={v or 'N/D'}" for k, v in niveles_normalizados.items())
            resultado.detalle = f"Nivel distinto entre fuentes ({detalle_niveles})."
        elif hay_vacios and resultado.tipo_inconsistencia == TipoInconsistencia.OK:
            resultado.tipo_inconsistencia = TipoInconsistencia.NIVEL_FALTANTE
            fuentes_sin_nivel = [k for k, v in niveles_normalizados.items() if not v]
            resultado.detalle = f"Nivel no especificado o no reconocido en: {', '.join(fuentes_sin_nivel)}."
        elif resultado.tipo_inconsistencia == TipoInconsistencia.OK and nivel_comp_nombre == NivelComparacion.NORMALIZADA:
            resultado.tipo_inconsistencia = TipoInconsistencia.COINCIDE_NORMALIZADO
            resultado.detalle = "Mismo puesto y nivel; difieren en formato de escritura (mayúsculas/acentos/espacios)."
        elif resultado.tipo_inconsistencia == TipoInconsistencia.OK and nivel_comp_nombre == NivelComparacion.EQUIVALENCIA_INSTITUCIONAL:
            resultado.tipo_inconsistencia = TipoInconsistencia.COINCIDE_EQUIVALENCIA
            resultado.detalle = "Mismo puesto mediante equivalencia institucional (abreviatura reconocida)."

    # --- Validación informativa contra el catálogo oficial de niveles ---
    # No cambia tipo_inconsistencia (podría dar falsos positivos en títulos
    # que "heredan" una palabra de la jerarquía, ver catalogo_niveles.py);
    # se reporta aparte para que el usuario lo revise si quiere.
    advertencias = []
    for f in fuentes_presentes:
        aviso = validar_nivel_catalogo(f.puesto_normalizado, f.nivel_normalizado)
        if aviso:
            advertencias.append(f"{f.fuente.value}: {aviso}")
        aviso_abrev = detectar_posible_abreviatura_no_reconocida(f.puesto_original)
        if aviso_abrev:
            advertencias.append(f"{f.fuente.value}: {aviso_abrev}")
    resultado.advertencia_catalogo = " ".join(advertencias)

    return resultado


def _marcar_duplicados(grupos: Dict[str, List[PuestoRecord]], resultados: List[ComparisonResult], fuente: Fuente):
    """Genera resultados adicionales de tipo Duplicado para claves con >1 registro en una misma fuente."""
    duplicados_resultados = []
    for clave, registros in grupos.items():
        if len(registros) <= 1:
            continue
        niveles = set(r.nivel_normalizado for r in registros if r.nivel_normalizado)
        tipo = (
            TipoInconsistencia.DUPLICADO_NIVEL_DISTINTO if len(niveles) > 1
            else TipoInconsistencia.DUPLICADO
        )
        ubicaciones = "; ".join(r.ubicacion.resumen() if r.ubicacion else "?" for r in registros)
        for r in registros:
            res = ComparisonResult(
                puesto_clave_normalizada=f"[DUP-{fuente.value}] {clave}",
                tipo_inconsistencia=tipo,
                detalle=f"Puesto duplicado {len(registros)} veces dentro de {fuente.value}. Ubicaciones: {ubicaciones}",
            )
            setattr(res, {"Excel": "excel", "Word": "word", "Organigrama": "organigrama"}[fuente.value], r)
            duplicados_resultados.append(res)
    resultados.extend(duplicados_resultados)


def comparar_fuentes(
    excel_records: List[PuestoRecord],
    word_records: List[PuestoRecord],
    organigrama_records: List[PuestoRecord],
    incluir_word: bool = True,
) -> List[ComparisonResult]:
    """
    incluir_word=False es el modo "Excel vs Organigrama" (ver
    pipeline.ModoAnalisis.EXCEL_ORGANIGRAMA): Word se excluye por completo
    de la clasificación de faltantes/adicionales, aunque `word_records`
    venga vacío igualmente en ese caso. Se expone como parámetro explícito
    (en vez de inferirlo de si word_records está vacío) para que un Word
    genuinamente sin puestos extraídos, en modo COMPLETO, sí se siga
    reportando como "falta en Word" — son escenarios distintos.
    """
    resultados: List[ComparisonResult] = []

    # 1. Registros con error -> resultado directo
    fuentes_a_procesar = [excel_records, organigrama_records] + ([word_records] if incluir_word else [])
    for lista in fuentes_a_procesar:
        for r in lista:
            if not r.valido:
                resultados.append(_resultado_desde_error(r))

    validos_excel = [r for r in excel_records if r.valido]
    validos_word = [r for r in word_records if r.valido] if incluir_word else []
    validos_org = [r for r in organigrama_records if r.valido]

    # Agrupación "cruda" (sin expandir abreviaturas): se usa para reporte y
    # para detectar duplicados DENTRO de cada fuente.
    excel_groups = _agrupar_por_normalizado(validos_excel)
    word_groups_crudo = _agrupar_por_normalizado(validos_word)
    org_groups_crudo = _agrupar_por_normalizado(validos_org)

    # 2. Duplicados dentro de cada fuente (se reportan aparte, no interfieren con el matching)
    _marcar_duplicados(excel_groups, resultados, Fuente.EXCEL)
    _marcar_duplicados(word_groups_crudo, resultados, Fuente.WORD)
    _marcar_duplicados(org_groups_crudo, resultados, Fuente.ORGANIGRAMA)

    # Agrupación por CLAVE DE COMPARACIÓN (abreviaturas expandidas): esta es
    # la que se usa para emparejar entre fuentes distintas.
    excel_comp = _agrupar_por_clave_comparacion(validos_excel)
    word_comp = _agrupar_por_clave_comparacion(validos_word)
    org_comp = _agrupar_por_clave_comparacion(validos_org)

    claves_excel = list(excel_comp.keys())

    # 3. Emparejamiento GLOBAL (no voraz por orden) Excel<->Word y Excel<->Organigrama
    asignacion_word = _emparejar_conjunto(claves_excel, word_comp)
    asignacion_org = _emparejar_conjunto(claves_excel, org_comp)

    prioridad = {
        NivelComparacion.EXACTA: 0, NivelComparacion.NORMALIZADA: 1,
        NivelComparacion.EQUIVALENCIA_INSTITUCIONAL: 2,
        NivelComparacion.FUZZY_ALTA: 3, NivelComparacion.FUZZY_REVISION: 4,
        NivelComparacion.SIN_COINCIDENCIA: 5,
    }

    def _nivel_comparacion_desde_match(match: Optional[dict], excel_rec, otro_rec) -> NivelComparacion:
        if match is None:
            return NivelComparacion.SIN_COINCIDENCIA
        if match["nivel"] == "exacta_o_normalizada":
            if otro_rec.puesto_original == excel_rec.puesto_original:
                return NivelComparacion.EXACTA
            if otro_rec.puesto_normalizado == excel_rec.puesto_normalizado:
                return NivelComparacion.NORMALIZADA
            # la clave de comparación (con abreviaturas expandidas) coincide,
            # pero el texto normalizado crudo NO -> la coincidencia dependió
            # de una equivalencia institucional (J.U.D., L.C.P., etc.)
            return NivelComparacion.EQUIVALENCIA_INSTITUCIONAL
        return NivelComparacion.FUZZY_ALTA if match["nivel"] == "fuzzy_alta" else NivelComparacion.FUZZY_REVISION

    for clave_excel in claves_excel:
        excel_rec = excel_comp[clave_excel][0]  # representativo; duplicados ya reportados aparte

        match_word = asignacion_word.get(clave_excel)
        word_rec = word_comp[match_word["destino"]][0] if match_word else None
        nivel_nombre_word = _nivel_comparacion_desde_match(match_word, excel_rec, word_rec)
        score_word = match_word["score"] if match_word else 0.0
        detalle_word = match_word["motivo"] if match_word else ""

        match_org = asignacion_org.get(clave_excel)
        org_rec = org_comp[match_org["destino"]][0] if match_org else None
        nivel_nombre_org = _nivel_comparacion_desde_match(match_org, excel_rec, org_rec)
        score_org = match_org["score"] if match_org else 0.0
        detalle_org = match_org["motivo"] if match_org else ""

        # nivel de comparación de nombre global = el peor de los dos (más conservador)
        candidatos_nivel = [n for n in (nivel_nombre_word, nivel_nombre_org) if n != NivelComparacion.SIN_COINCIDENCIA]
        # Si no hubo ningún candidato de comparación (el puesto solo existe en
        # Excel), no hay ambigüedad de nombre que reportar: se usa EXACTA para
        # que la clasificación final dependa únicamente de "faltantes".
        nivel_nombre_final = max(candidatos_nivel, key=lambda n: prioridad[n]) if candidatos_nivel else NivelComparacion.EXACTA

        confianza_final = min([s for s in (score_word, score_org, 100.0) if s > 0] or [100.0])
        detalle_match = " ".join(d for d in (detalle_word, detalle_org) if d)

        nota_equivalencia = ""
        if word_rec is not None:
            nota_equivalencia = _nota_equivalencia_aplicada(excel_rec, word_rec)
        if not nota_equivalencia and org_rec is not None:
            nota_equivalencia = _nota_equivalencia_aplicada(excel_rec, org_rec)

        # clave de reporte: se muestra la versión SIN expandir (más legible,
        # reconocible por el usuario) tomada del propio registro de Excel.
        clave_reporte = excel_rec.puesto_normalizado
        resultado = _construir_resultado(
            clave_reporte, excel_rec, word_rec, org_rec, nivel_nombre_final, confianza_final, detalle_match,
            incluir_word=incluir_word,
        )
        resultado.equivalencia_aplicada = nota_equivalencia
        resultado.puesto_canonico = normalizar_para_comparacion(excel_rec.puesto_normalizado)
        resultados.append(resultado)

    # 4. Claves de Word/Organigrama que no se emparejaron con ningún Excel -> "puesto adicional"
    claves_word_usadas = {m["destino"] for m in asignacion_word.values()}
    claves_org_usadas = {m["destino"] for m in asignacion_org.values()}
    word_comp_restante = {k: v for k, v in word_comp.items() if k not in claves_word_usadas}
    org_comp_restante = {k: v for k, v in org_comp.items() if k not in claves_org_usadas}

    asignacion_word_org = _emparejar_conjunto(list(word_comp_restante.keys()), org_comp_restante)

    for clave_word in word_comp_restante:
        word_rec = word_comp_restante[clave_word][0]
        match = asignacion_word_org.get(clave_word)
        org_rec = org_comp_restante[match["destino"]][0] if match else None
        nivel_nombre = _nivel_comparacion_desde_match(match, word_rec, org_rec) if match else NivelComparacion.NORMALIZADA
        confianza = match["score"] if match else 100.0
        detalle = match["motivo"] if match else ""
        clave_reporte = word_rec.puesto_normalizado
        resultado = _construir_resultado(clave_reporte, None, word_rec, org_rec, nivel_nombre, confianza, detalle, incluir_word=incluir_word)
        if org_rec is not None:
            resultado.equivalencia_aplicada = _nota_equivalencia_aplicada(word_rec, org_rec)
        resultado.puesto_canonico = normalizar_para_comparacion(word_rec.puesto_normalizado)
        resultados.append(resultado)

    claves_org_usadas_en_restantes = {m["destino"] for m in asignacion_word_org.values()}
    for clave_org in org_comp_restante:
        if clave_org in claves_org_usadas_en_restantes:
            continue
        org_rec = org_comp_restante[clave_org][0]
        clave_reporte = org_rec.puesto_normalizado
        resultado = _construir_resultado(clave_reporte, None, None, org_rec, NivelComparacion.NORMALIZADA, 100.0, "", incluir_word=incluir_word)
        resultado.puesto_canonico = normalizar_para_comparacion(org_rec.puesto_normalizado)
        resultados.append(resultado)

    logger.info(f"Comparación finalizada: {len(resultados)} resultado(s) generado(s).")
    return resultados


def aplicar_segunda_opinion_ollama(resultados: List[ComparisonResult]) -> List[ComparisonResult]:
    """
    Paso OPCIONAL de post-procesamiento (§29-42): para cada resultado que
    quedó en "Requiere revisión" tras el matching determinista, consulta a
    Ollama como segunda opinión semántica. Si config.OLLAMA_ENABLED es
    False (por defecto), esta función no hace nada y regresa los
    resultados sin cambios — el resto del sistema no depende de esto.

    Ollama NUNCA determina el nivel ni sustituye al catálogo: solo puede
    mover un caso de "Requiere revisión" a "Coincidencia resuelta por IA"
    cuando responde con alta confianza que sí es el mismo puesto, o
    dejarlo igual (revisión manual) en cualquier otro caso — nunca lo
    marca como coincidencia si la evidencia no es suficiente.
    """
    if not config.OLLAMA_ENABLED:
        return resultados

    for r in resultados:
        if r.tipo_inconsistencia != TipoInconsistencia.REQUIERE_REVISION:
            continue

        registros_presentes = [f for f in (r.excel, r.word, r.organigrama) if f is not None]
        if len(registros_presentes) < 2:
            continue
        base = registros_presentes[0]
        otro = registros_presentes[1]

        respuesta = consultar_ollama(
            base.puesto_original, otro.puesto_original,
            base.tipo_puesto, base.niveles_catalogo,
        )
        if respuesta is None:
            continue  # Ollama no disponible o respuesta inválida -> se queda en revisión manual

        r.ia_consultada = True
        r.ia_explicacion = respuesta.get("explicacion", "")

        if (
            respuesta["es_mismo_puesto"]
            and not respuesta["requiere_revision_humana"]
            and respuesta["confianza"] >= config.OLLAMA_CONFIANZA_MINIMA_PARA_ACEPTAR
        ):
            r.tipo_inconsistencia = TipoInconsistencia.COINCIDE_IA
            r.metodo_coincidencia = MetodoCoincidencia.IA
            r.confianza_match = round(respuesta["confianza"] * 100, 1)
            r.detalle = f"Confirmado por IA (Ollama): {respuesta['explicacion']}"
        # si Ollama dice que no, o no tiene suficiente confianza, el
        # resultado se queda tal cual (Requiere revisión / revisión manual)

    return resultados
