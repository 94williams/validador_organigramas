"""Comparación por ocurrencia: el ID nunca se deduce del nombre ni se renumera."""
from collections import Counter

from comparison.homologation import clave_homologada, verificar_homologacion
from models.models import NivelComparacion, TipoInconsistencia
from normalization.normalizer import normalizar_para_comparacion


def _clave(texto):
    return normalizar_para_comparacion(texto or "")


def _candidatos(excel, registros, usar_jefe):
    candidatos = [(i, r) for i, r in enumerate(registros, 1)
                  if r.valido and clave_homologada(r) == clave_homologada(excel)]
    if usar_jefe and excel.jefe_inmediato:
        candidatos = [(i, r) for i, r in candidatos if r.jerarquia_verificada
                      and _clave(r.jefe_inmediato) == _clave(excel.jefe_inmediato)]
    if len(candidatos) > 1 and excel.nivel_normalizado:
        iguales = [(i, r) for i, r in candidatos if r.nivel_normalizado == excel.nivel_normalizado]
        if iguales:
            candidatos = iguales
    return candidatos


def _jefe(excel, org, nombres_excel, nombres_org):
    if org is None or not org.jerarquia_verificada:
        return "No verificable"
    if not excel.jefe_inmediato:
        return "Sin referencia en Excel"
    if excel.jefe_inmediato.startswith("[ID de jefe no resoluble:"):
        return "No verificable"
    # Un nombre de superior repetido no identifica una rama de forma inequívoca.
    if nombres_excel[_clave(excel.jefe_inmediato)] > 1 or nombres_org[_clave(excel.jefe_inmediato)] > 1:
        return "Jefe ambiguo"
    return "Coincide" if _clave(excel.jefe_inmediato) == _clave(org.jefe_inmediato) else "Jefe inmediato diferente"


def _revisar_fuente(excel, registros, fuente, orden_verificado):
    candidatos = _candidatos(excel, registros, fuente == "Organigrama")
    if not orden_verificado:
        # Se puede comparar un nombre único, pero nunca certificar su posición.
        rec = candidatos[0][1] if len(candidatos) == 1 else None
        return rec, None, "No verificable", f"{fuente}: orden no verificable; revisar extracción o conexiones."
    pos = excel.id_excel
    actual = registros[pos - 1] if pos <= len(registros) else None
    if fuente == "Organigrama" and (excel.jefe_inmediato or "").startswith("[ID de jefe no resoluble:"):
        return actual, pos if actual else None, "No verificable", "Organigrama: corregir la referencia de jefe inmediato del Excel."
    nombre_igual = actual is not None and clave_homologada(actual) == clave_homologada(excel)
    jefe_igual = (fuente != "Organigrama" or not excel.jefe_inmediato
                  or _clave(actual.jefe_inmediato if actual else "") == _clave(excel.jefe_inmediato))
    if nombre_igual and jefe_igual:
        repetidos = sum(clave_homologada(r) == clave_homologada(excel)
                        and r.nivel_normalizado == excel.nivel_normalizado for r in registros)
        nota = (" Nombre/nivel repetidos: coincide por posición; Word no permite verificar el jefe inmediato."
                if fuente == "Word" and repetidos > 1 else "")
        return actual, pos, "Misma posición", f"{fuente}: coincide en posición {pos}." + nota
    posiciones = [i for i, _ in candidatos]
    if len(posiciones) == 1:
        estado = "Diferente posición"
        texto = f"Encontrado en diferente posición; realizar ajuste. {fuente}: posición {posiciones[0]}; esperada {pos} según Excel."
    elif posiciones:
        estado = "Coincidencia ambigua"
        texto = f"{fuente}: coincidencia ambigua en posiciones {', '.join(map(str, posiciones))}; esperada {pos}."
    elif nombre_igual:
        estado = "Jefe inmediato diferente"
        texto = f"{fuente}: el nombre coincide en posición {pos}, pero pertenece a otro jefe inmediato."
    else:
        estado = "Puesto no encontrado"
        texto = f"{fuente}: puesto esperado no encontrado; revisar la posición {pos}."
    if actual:
        texto += f" En la posición esperada se leyó «{actual.puesto_original}»."
    return actual, pos if actual else None, estado, texto


def comparar_por_id(excel, word, org, incluir_word):
    # Importación local para reutilizar reglas de nivel/catálogo sin crear un ciclo.
    from comparison.comparator import _construir_resultado, _resultado_desde_error, _nota_equivalencia_aplicada

    fuentes = {"Organigrama": org}
    if incluir_word:
        fuentes["Word"] = word
    validos = {f: [r for r in rs if r.valido] for f, rs in fuentes.items()}
    verificables = {f: bool(rs) and all(r.valido for r in rs) for f, rs in fuentes.items()}
    verificables["Organigrama"] = verificables["Organigrama"] and all(
        r.jerarquia_verificada and not r.error_orden and r.posicion_lectura == i
        for i, r in enumerate(org, 1))
    ids = Counter(r.id_excel for r in excel if r.id_excel is not None)
    nombres_org = Counter(clave_homologada(r) for r in org if r.valido)
    nombres_excel = Counter(clave_homologada(r) for r in excel if r.valido)
    resultados = []
    usados = {f: set() for f in fuentes}
    for e in sorted(excel, key=lambda r: (r.id_excel is None, r.id_excel or 0)):
        if not e.valido:
            resultados.append(_resultado_desde_error(e))
            continue
        error_id = e.error_id or ("ID vacío o inválido." if not isinstance(e.id_excel, int) or isinstance(e.id_excel, bool) or e.id_excel <= 0 else
                                  f"ID repetido: {e.id_excel}." if ids[e.id_excel] > 1 else "")
        comprobaciones = {f: _revisar_fuente(e, validos[f], f, verificables[f])
                          for f in fuentes} if not error_id else {}
        for f, (registro, posicion, estado, nota) in list(comprobaciones.items()):
            if not verificables[f] and registro is not None and id(registro) in usados[f]:
                comprobaciones[f] = (None, None, "No verificable", f"{f}: nombre repetido sin posición verificable; no se reutiliza otra aparición.")
        w = comprobaciones.get("Word", (None,))[0]
        o = comprobaciones.get("Organigrama", (None,))[0]
        presentes = [r for r in (e, w, o) if r is not None]
        mismos_nombres = len({clave_homologada(r) for r in presentes}) == 1
        nivel = (NivelComparacion.EXACTA if len({r.puesto_original for r in presentes}) == 1 else
                 NivelComparacion.EQUIVALENCIA_INSTITUCIONAL if mismos_nombres else NivelComparacion.FUZZY_REVISION)
        r = _construir_resultado(e.puesto_normalizado, e, w, o, nivel, 100 if mismos_nombres else 0,
                                "Puesto diferente en la posición esperada por el ID de Excel.", incluir_word)
        r.revision_por_id = True
        r.puesto_canonico = clave_homologada(e)
        r.equivalencia_aplicada = " ".join(_nota_equivalencia_aplicada(e, otro) for otro in (w, o) if otro)
        r.estado_jefe = _jefe(e, o, nombres_excel, nombres_org)
        notas = []
        for f, (registro, posicion, estado, nota) in comprobaciones.items():
            campo = "word" if f == "Word" else "organigrama"
            setattr(r, "posicion_" + campo, posicion)
            setattr(r, "orden_" + campo, estado)
            notas.append(nota)
            if registro is not None:
                usados[f].add(id(registro))
        if error_id:
            r.estado_orden = "Revisar ID de Excel"
            notas.append(error_id)
        else:
            estados = [c[2] for c in comprobaciones.values()]
            r.estado_orden = next((s for s in ("No verificable", "Coincidencia ambigua", "Puesto no encontrado",
                                              "Diferente posición", "Jefe inmediato diferente") if s in estados), "Misma posición")
        if e.jefe_inmediato and e.jefe_inmediato.startswith("[ID de jefe no resoluble:"):
            r.estado_orden = "No verificable"
            notas.append(f"Excel: {e.jefe_inmediato}; corregir la referencia del jefe inmediato.")
        if r.estado_jefe in ("Jefe ambiguo", "Jefe inmediato diferente"):
            notas.append(f"Jefe inmediato: {r.estado_jefe}. Excel: «{e.jefe_inmediato}»; organigrama: «{o.jefe_inmediato if o else '—'}».")
            if r.estado_orden == "Misma posición":
                r.estado_orden = r.estado_jefe
        for otro in (w, o):
            if otro and otro.nivel_normalizado != e.nivel_normalizado:
                notas.append(f"Nivel: Excel={e.nivel_original or 'N/D'}; {otro.fuente.value}={otro.nivel_original or 'N/D'}.")
        if o is None and not verificables["Organigrama"]:
            notas.extend(dict.fromkeys(x.error_orden for x in org if x.error_orden))
        r.detalle_orden = " ".join(notas)
        if error_id or any(not verificables[f] and c[0] is None for f, c in comprobaciones.items()):
            r.tipo_inconsistencia = TipoInconsistencia.REQUIERE_REVISION
            r.detalle = "No se puede asignar una aparición con certeza; revisar el detalle de orden."

        if error_id or r.estado_orden != "Misma posición":
            if r.tipo_inconsistencia in (TipoInconsistencia.OK, TipoInconsistencia.COINCIDE_NORMALIZADO,
                                        TipoInconsistencia.COINCIDE_EQUIVALENCIA):
                r.tipo_inconsistencia = TipoInconsistencia.REQUIERE_REVISION
        # En modo por ID los nombres iguales en varias filas son ocurrencias, no duplicados.
        verificar_homologacion([r], [e], [w] if w else [], [o] if o else [], incluir_word)
        resultados.append(r)

    for f, registros in fuentes.items():
        for i, registro in enumerate(registros, 1):
            if not registro.valido:
                resultados.append(_resultado_desde_error(registro))
                continue
            if id(registro) in usados[f]:
                continue
            r = _construir_resultado(registro.puesto_normalizado, None,
                                    registro if f == "Word" else None, registro if f == "Organigrama" else None,
                                    NivelComparacion.EXACTA, 0, incluir_word=incluir_word)
            r.revision_por_id = True
            if any(e.error_id or not e.id_excel or ids[e.id_excel] > 1 for e in excel) or not verificables[f]:
                r.tipo_inconsistencia = TipoInconsistencia.REQUIERE_REVISION
                r.detalle = "Aparición sin referencia asignada; no se puede confirmar que sea adicional."
            r.estado_orden = "Sin referencia asignada"
            r.detalle_orden = f"{f}: aparición sin ID de Excel asignado; revisar puestos adicionales o IDs pendientes."
            setattr(r, "posicion_word" if f == "Word" else "posicion_organigrama", i if verificables[f] else None)
            resultados.append(r)
    return resultados
