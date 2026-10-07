"""Orden jerárquico conservador de cajas enlazadas por conectores ortogonales.

Solo certifica un árbol completo, de arriba hacia abajo. No interpreta cruces
sin unión explícita, conectores curvos, OCR ni continuaciones entre páginas.
"""
from math import hypot

TOL = 2.0  # puntos PDF; absorbe redondeos del exportador, no distancias entre cajas


def _dist(p, segmento):
    a, b = segmento
    dx, dy = b[0]-a[0], b[1]-a[1]
    t = max(0, min(1, ((p[0]-a[0])*dx+(p[1]-a[1])*dy)/(dx*dx+dy*dy))) if dx or dy else 0
    return hypot(p[0]-a[0]-t*dx, p[1]-a[1]-t*dy)


def _borde(segmento, caja):
    x0,y0,x1,y1 = caja
    lados = [((x0,y0),(x1,y0)), ((x1,y0),(x1,y1)), ((x1,y1),(x0,y1)), ((x0,y1),(x0,y0))]
    return any(all(_dist(p,lado)<=TOL for p in segmento) for lado in lados)


def _puertos(segmentos, caja):
    x0,y0,x1,y1 = caja
    lados = {'arriba':((x0,y0),(x1,y0)), 'abajo':((x0,y1),(x1,y1)),
             'izquierda':((x0,y0),(x0,y1)), 'derecha':((x1,y0),(x1,y1))}
    return {nombre for nombre,lado in lados.items()
            if any(_dist(p,lado)<=TOL for segmento in segmentos for p in segmento)}


def ordenar_por_ramas(page, registros):
    def no_verificable(motivo):
        for registro in registros:
            registro.error_orden = 'Orden no verificable; revisar conexión. ' + motivo
        return registros

    if not registros:
        return registros
    cajas = [r.ubicacion.bbox for r in registros]
    segmentos = []
    geometria_no_soportada = False
    for dibujo in page.get_drawings():
        if dibujo.get('type') == 'f':  # rellenos, sin trazo de conexión
            continue
        rect = dibujo.get('rect')
        if rect and any(all(abs(rect[i]-c[i])<=TOL for i in range(4)) for c in cajas):
            continue
        for item in dibujo.get('items', []):
            if item[0] == 'c':
                geometria_no_soportada = True
            if item[0] != 'l':
                continue
            a,b = tuple(item[1]),tuple(item[2]); segmento=(a,b)
            if any(_borde(segmento,c) for c in cajas):
                continue
            if hypot(b[0]-a[0], b[1]-a[1])<=TOL:
                continue
            if abs(a[0]-b[0])>TOL and abs(a[1]-b[1])>TOL:
                # No inferir la dirección a partir de flechas o diagonales.
                geometria_no_soportada = True
                continue
            segmentos.append(segmento)
    if geometria_no_soportada:
        return no_verificable('Hay trazos curvos o diagonales que requieren revisión.')
    if len(registros)==1 and not segmentos:
        return registros

    # Componentes de conectores: incluye uniones en T (extremo contra segmento).
    vecinos = [set() for _ in segmentos]
    for i,s in enumerate(segmentos):
        for j in range(i):
            otro = segmentos[j]
            unidos = any(_dist(p,otro)<=TOL for p in s) or any(_dist(p,s)<=TOL for p in otro)
            if unidos:
                vecinos[i].add(j); vecinos[j].add(i)
            else:
                # Un cruce interior puede ser puente o unión. No inventar parentesco.
                vertical, horizontal = (s,otro) if abs(s[0][0]-s[1][0])<=TOL else (otro,s)
                if (abs(vertical[0][0]-vertical[1][0])<=TOL and abs(horizontal[0][1]-horizontal[1][1])<=TOL
                    and min(horizontal[0][0],horizontal[1][0]) < vertical[0][0] < max(horizontal[0][0],horizontal[1][0])
                    and min(vertical[0][1],vertical[1][1]) < horizontal[0][1] < max(vertical[0][1],vertical[1][1])):
                    return no_verificable('Cruce de conectores sin unión inequívoca.')
    componentes=[]; visitados=set()
    for i in range(len(segmentos)):
        if i in visitados:
            continue
        pila=[i]; componente=[]; visitados.add(i)
        while pila:
            n=pila.pop(); componente.append(segmentos[n])
            for vecino in vecinos[n]-visitados:
                visitados.add(vecino);pila.append(vecino)
        componentes.append(componente)

    padres={}; hijos={i:set() for i in range(len(cajas))}
    for componente in componentes:
        puertos={i:_puertos(componente,c) for i,c in enumerate(cajas)}
        puertos={i:p for i,p in puertos.items() if p}
        if not puertos:
            continue  # decoración sin conexión con puestos
        candidatos=[i for i,p in puertos.items() if p=={'abajo'}]
        dependientes=[i for i,p in puertos.items() if p=={'arriba'}]
        if len(candidatos)!=1 or not dependientes or len(dependientes)+1!=len(puertos):
            return no_verificable('Conector incompleto, lateral o con más de un posible superior.')
        padre=candidatos[0]
        for hijo in dependientes:
            if cajas[padre][3]>=cajas[hijo][1]-TOL or (hijo in padres and padres[hijo]!=padre):
                return no_verificable('Jerarquía ambigua o puesto con más de un superior.')
            padres[hijo]=padre;hijos[padre].add(hijo)
    raices=[i for i in hijos if i not in padres]
    if len(raices)!=1:
        return no_verificable('No se reconoce un único árbol completo de puestos.')
    orden=[]; pila=[raices[0]]
    while pila:
        actual=pila.pop()
        if actual in orden:
            return no_verificable('Ciclo en las conexiones.')
        orden.append(actual)
        hijos_ordenados=sorted(hijos[actual], key=lambda i:(cajas[i][0],cajas[i][1]))
        pila.extend(reversed(hijos_ordenados))
    if len(orden)!=len(registros):
        return no_verificable('Hay puestos desconectados del árbol.')
    return [registros[i] for i in orden]
