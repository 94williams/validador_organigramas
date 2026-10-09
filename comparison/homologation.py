"""Compara nombres homologados sin posiciones ni aprobación implícita de niveles."""
from collections import Counter
from rapidfuzz.fuzz import ratio

from normalization.display_name import homologar_puesto
from normalization.normalizer import normalizar_puesto, normalizar_para_comparacion


def clave_homologada(registro):
    return normalizar_para_comparacion(normalizar_puesto(homologar_puesto(registro.puesto_original)))


def verificar_homologacion(resultados, excel, word, organigrama, incluir_word=True):
    fuentes = {"Excel": excel, "Organigrama": organigrama}
    if incluir_word:
        fuentes["Word"] = word
    conteos = {nombre: Counter(clave_homologada(r) for r in registros if r.valido)
               for nombre, registros in fuentes.items()}
    pares = [("Excel", "Organigrama")]
    if incluir_word:
        pares = [("Excel", "Word"), ("Excel", "Organigrama"), ("Word", "Organigrama")]
    for resultado in resultados:
        registros = {"Excel": resultado.excel, "Word": resultado.word, "Organigrama": resultado.organigrama}
        comparaciones = {}
        similitudes = []
        for a, b in pares:
            ra, rb = registros[a], registros[b]
            if ra is None or rb is None or not ra.valido or not rb.valido:
                estado = "No comparable"
            elif conteos[a][clave_homologada(ra)] > 1 or conteos[b][clave_homologada(rb)] > 1:
                estado = "Revisar duplicados"
            else:
                ca, cb = clave_homologada(ra), clave_homologada(rb)
                estado = "Coinciden" if ca == cb else "No coinciden"
                # Reservar 100 para igualdad, incluso después del redondeo.
                similitudes.append(100.0 if ca == cb else min(99.9, round(ratio(ca, cb), 1)))
            comparaciones[f"{a} vs {b}"] = estado
        resultado.comparaciones_homologadas = comparaciones
        estados = set(comparaciones.values())
        # El detalle por pareja permite conservar más de una incidencia.
        resultado.estado_homologacion = next(
            (estado for estado in ("Revisar duplicados", "No comparable", "No coinciden") if estado in estados),
            "Coinciden",
        )

        resultado.similitud_homologada = (
            min(similitudes) if len(similitudes) == len(pares) else None
        )
