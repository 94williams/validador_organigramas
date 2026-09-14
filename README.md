# Validador de Puestos y Niveles (Excel · Word · Organigrama)

Herramienta en Python que compara tres fuentes de información de puestos y niveles organizacionales —un **Excel** de referencia, un **documento Word** (o su PDF) y un **organigrama de Visio exportado a PDF**— y genera un reporte Excel con todas las inconsistencias detectadas, con trazabilidad hasta el origen exacto de cada dato.

---

## 1. Instalación

Requiere Python 3.10+.

```bash
cd proyecto
pip install -r requirements.txt
```

### OCR (opcional)

Solo es necesario si vas a procesar PDFs **escaneados** (sin texto seleccionable). Además de `pytesseract`/`pillow` (ya en `requirements.txt`), necesitas el binario de Tesseract instalado en el sistema:

**Windows:** descarga el instalador desde https://github.com/UB-Mannheim/tesseract/wiki e instala también el paquete de idioma español.

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-spa
```

Si un PDF tiene texto seleccionable, el sistema **nunca** usa OCR (se extrae directamente), así que en la mayoría de los casos esto ni siquiera se necesita.

---

## 2. Uso

### Modos de análisis

La herramienta soporta dos modos, seleccionables en la interfaz o por línea de comandos:

| Modo | Fuentes | Word participa |
|---|---|---|
| **Completo** (por defecto) | Excel + Word + Organigrama | Sí |
| **Excel vs Organigrama** | Excel + Organigrama | No — no se solicita, no se compara, no aparece en resultados ni en el resumen |

Word nunca se elimina del proyecto: en modo "Excel vs Organigrama" simplemente no participa en esa ejecución en particular. Ambos modos comparten exactamente la misma lógica de extracción, normalización, catálogo y comparación — la arquitectura permite agregar más modos en el futuro (ej. "Word vs Organigrama") sin duplicar nada de esa lógica, solo decidiendo qué extractores se llaman.

### Interfaz gráfica (recomendada)

```bash
streamlit run ui/app.py
```

Se abre en el navegador (`http://localhost:8501`). Flujo:

1. Elegir el modo de análisis en la barra lateral.
2. Cargar el Excel de referencia (opcionalmente indicar el nombre de hoja).
3. Cargar el PDF del organigrama.
4. Si el modo es "Completo", cargar también el documento Word (`.docx` o `.pdf`) — este campo se oculta automáticamente en modo "Excel vs Organigrama".
5. Presionar **"Analizar documentos"**.
6. Revisar el resumen y la tabla filtrable de inconsistencias.
7. Descargar el Excel de resultados.

### Uso programático

```python
from pipeline import ejecutar_analisis, exportar_reporte, ModoAnalisis

# Modo completo (Excel + Word + Organigrama)
resultado = ejecutar_analisis(
    ruta_excel="referencia.xlsx",
    ruta_organigrama_pdf="organigrama.pdf",
    ruta_word="documento.docx",   # o "documento.pdf"
    hoja_excel=None,               # opcional
    modo=ModoAnalisis.COMPLETO,    # valor por defecto, se puede omitir
)

# Modo Excel vs Organigrama (Word no participa)
resultado = ejecutar_analisis(
    ruta_excel="referencia.xlsx",
    ruta_organigrama_pdf="organigrama.pdf",
    modo=ModoAnalisis.EXCEL_ORGANIGRAMA,
)

exportar_reporte(
    resultado["resultados"], "reporte_inconsistencias.xlsx",
    resultado["excel_records"], resultado["word_records"], resultado["organigrama_records"],
    modo=resultado["modo"],
)
```

### Línea de comandos

```bash
# Completo
python main.py --excel referencia.xlsx --organigrama organigrama.pdf --word documento.docx

# Excel vs Organigrama
python main.py --modo excel_organigrama --excel referencia.xlsx --organigrama organigrama.pdf
```

---

## 2.1 Acceso local, red local y remoto

### Solo en tu máquina (por defecto)

```bash
streamlit run ui/app.py
```

Solo tú puedes entrar, vía `http://localhost:8501`.

### Compartir con tu equipo en la misma red (oficina)

El proyecto ya viene configurado (`.streamlit/config.toml`) para escuchar en toda la red, no solo en `localhost`. Usa el script de arranque en vez de `streamlit run` directo:

**Windows** — doble clic en `start_server.bat`, o desde consola:
```cmd
start_server.bat
```

**Linux/Mac**:
```bash
./start_server.sh
```

El script imprime tu IP local automáticamente. Compártela con tu equipo: `http://TU-IP-LOCAL:8501`. Cualquiera en la misma red de la oficina puede entrar sin instalar nada, solo con un navegador.

Para cambiar el puerto (por si el 8501 está ocupado):
```bash
# Windows
set VALIDADOR_PORT=9000 && start_server.bat
# Linux/Mac
VALIDADOR_PORT=9000 ./start_server.sh
```

**Importante:** esto expone la app a *toda* tu red local, no solo a tu equipo — cualquiera conectado al mismo WiFi/switch podría entrar si conoce o adivina la IP y el puerto. Si tu red de oficina es compartida con más gente de la que debería tener acceso, activa la contraseña (ver más abajo) o usa Tailscale también dentro de la oficina.

### Acceso remoto (fuera de la red de la oficina)

Tu red de trabajo tiene protocolos de seguridad, así que **no se recomienda abrir puertos en el router ni exponer el servidor directamente a internet** — ninguna de las dos cosas es necesaria.

**Recomendado: Tailscale.** Crea una red privada (VPN mesh) entre tu máquina y las de tu equipo, sin abrir ningún puerto público, funciona detrás de NAT/firewall corporativo, y es compatible con Windows/Mac/Linux. Cada persona entra con su cuenta (Google/Microsoft/etc.), y solo los dispositivos que tú autorices pueden conectarse — revocar el acceso de alguien es tan simple como quitarlo de tu cuenta de Tailscale.

Pasos:
1. En tu máquina (la que va a estar prendida 24/7): entra a [tailscale.com/download](https://tailscale.com/download), instala el cliente para Windows, inicia sesión con una cuenta (Google, Microsoft, GitHub, o email).
2. Repite la instalación en la máquina de cada persona de tu equipo que necesite acceso, usando la misma cuenta compartida del equipo o invitándolos a tu "tailnet" desde el panel de administración de Tailscale.
3. Una vez conectados, tu máquina tiene una IP privada tipo `100.x.y.z` (visible en el ícono de Tailscale en la bandeja del sistema). Corre `start_server.bat` / `start_server.sh` como en el paso anterior.
4. Tu equipo entra usando esa IP de Tailscale: `http://100.x.y.z:8501` — funciona exactamente igual sin importar en qué red esté cada quien, sin abrir ningún puerto en tu router.

Alternativas equivalentes si prefieres: [ZeroTier](https://www.zerotier.com/) (similar a Tailscale) o [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) (expone la app a través de la red de Cloudflare sin abrir puertos, útil si necesitas un link público en vez de una red privada). Tailscale es la opción más simple de administrar para un equipo pequeño.

### Protección con contraseña (recomendada si hay acceso remoto)

```bash
# Windows
set VALIDADOR_PASSWORD=una-clave-segura && start_server.bat
# Linux/Mac
VALIDADOR_PASSWORD=una-clave-segura ./start_server.sh
```

Con esto, la app pide una contraseña antes de mostrar cualquier contenido — una capa adicional de defensa, útil incluso dentro de Tailscale (defensa en profundidad). Sin esta variable, la app queda sin contraseña (comportamiento por defecto, adecuado si solo se usa dentro de la red local de confianza).

### Otras consideraciones de seguridad (§18)

- Los archivos que subes se guardan temporalmente y se borran automáticamente al iniciar un nuevo análisis (no quedan copias acumuladas).
- El límite de tamaño de archivo subido es 50 MB (`maxUploadSize` en `.streamlit/config.toml`, ajustable).
- Ningún dato sale de tu máquina ni de tu red — todo el procesamiento es local (ver sección de Privacidad). La única excepción es si activas Ollama apuntando a un servidor remoto, lo cual no es la configuración por defecto.

---

## 3. Estructura del proyecto

```
proyecto/
├── main.py / pipeline.py    # orquestación: extracción -> comparación -> reporte
├── config.py                 # umbrales, nombres de columnas, patrones (AJUSTAR AQUÍ)
├── requirements.txt
├── ui/
│   └── app.py                 # interfaz Streamlit
├── extractors/
│   ├── excel_extractor.py     # lectura flexible del Excel (detecta encabezados)
│   ├── pdf_utils.py           # utilidades comunes: texto vs. escaneado, OCR
│   ├── organigrama_extractor.py  # agrupación espacial de bloques de texto
│   └── word_extractor.py      # tablas desde .docx nativo o PDF (pdfplumber)
├── normalization/
│   └── normalizer.py          # normalización de puesto y nivel (nunca modifica el original)
├── comparison/
│   ├── matcher.py              # coincidencia exacta / normalizada / fuzzy con reglas
│   └── comparator.py           # comparación de 3 fuentes, duplicados, faltantes
├── reports/
│   └── excel_report.py         # genera el Excel de resultados (detalle + resumen)
├── models/
│   └── models.py               # PuestoRecord, ComparisonResult, enums
├── utils/
│   └── logger.py               # logging a archivo (logs/proceso.log)
└── tests/                      # pruebas unitarias e integración (pytest)
```

---

## 4. Cómo funciona (resumen del análisis)

1. **Extracción**: cada fuente se lee de forma independiente y nunca detiene el proceso completo si falla (los errores se acumulan y aparecen en el reporte como "Error de extracción").
   - **Excel**: se buscan encabezados reconocibles ("Puesto", "Nivel del puesto", etc.) en cualquier hoja; si no se encuentran, usa las columnas fijas J/K como respaldo (configurable en `config.py`).
   - **Word**: si tienes el `.docx` original, se procesa directamente (más confiable). Si solo tienes el PDF, se usa `pdfplumber` para detectar tablas.
   - **Organigrama**: se detectan los rectángulos vectoriales reales de cada caja del PDF (bordes que Visio dibuja al exportar) y se le asigna el texto que cae dentro de cada uno — mucho más confiable que agrupar por cercanía en organigramas densos con muchas columnas. Si una página no tiene cajas vectoriales detectables, se usa como respaldo la agrupación por cercanía espacial. Si la página es escaneada, se aplica OCR automáticamente. Validado contra un organigrama real de gobierno de 7 páginas y cientos de puestos, coincidiendo exactamente con los totales declarados en el documento.

2. **Normalización**: cada valor se convierte a una forma canónica (minúsculas, sin acentos, sin comillas/guiones raros, espacios colapsados) **sin tocar el valor original**, que se conserva para el reporte.

3. **Comparación**: el Excel se usa como referencia principal. Para cada puesto de Excel se busca su pareja en Word y Organigrama, primero por coincidencia exacta tras normalizar, y si no existe, por similitud aproximada (RapidFuzz) con una regla adicional que evita confundir puestos jerárquicamente distintos (p. ej. "Director" vs. "Subdirector") aunque el texto sea muy parecido.

4. **Reporte**: Excel con una hoja "Detalle" (filtrable, coloreada por tipo de inconsistencia, con la ubicación exacta de cada dato) y una hoja "Resumen" con conteos totales.

---

## 5. Tipos de inconsistencia que detecta

| Tipo | Significado |
|---|---|
| OK | Presente en las 3 fuentes, mismo nombre y nivel |
| Coincide después de normalización | Mismo puesto/nivel, pero difieren en formato (mayúsculas, acentos, espacios) |
| Posible coincidencia | Nombres muy similares pero no idénticos (alta confianza) |
| Requiere revisión | Similitud media, no concluyente — revisión manual necesaria |
| Nivel inconsistente | El nivel difiere entre fuentes |
| Nivel faltante | El nivel no está especificado o no se pudo reconocer en alguna fuente |
| Puesto faltante | Existe en Excel pero no en Word y/o Organigrama |
| Puesto adicional | Existe en Word/Organigrama pero no en Excel |
| Duplicado | El mismo puesto aparece más de una vez dentro de una misma fuente |
| Duplicado con nivel distinto | Igual que el anterior, pero con niveles distintos entre las repeticiones |
| Error de extracción | No se pudo leer un archivo/fila/celda; nunca detiene el resto del análisis |

Además de estos tipos, cada fila puede traer una **"Advertencia de catálogo"** aparte (columna independiente, no afecta la clasificación anterior): valida si el nivel capturado corresponde al catálogo oficial de niveles por tipo de puesto (configurable en `config.py`, ver sección 6). Es puramente informativa porque algunos títulos son excepciones conocidas (ej. "Secretaría Particular" no es nivel de Secretaría) — está pensada para que el usuario la revise, no para bloquear nada automáticamente.

---

## 6. Ajustar el comportamiento (sin tocar la lógica)

Todo esto se configura en `config.py`:

- **Nombres de columnas de Excel/Word** que se reconocen como "puesto" y "nivel" (`EXCEL_HEADERS_*`, `WORD_HEADERS_*`).
- **Columnas de respaldo** si no se detectan encabezados (por defecto J/K, según el planteamiento original).
- **Umbrales de fuzzy matching** (`FUZZY_UMBRAL_ALTA_CONFIANZA`, `FUZZY_UMBRAL_REVISION_MIN`).
- **Prefijos jerárquicos residuales** que no son tipos oficiales del catálogo pero indican jerarquía distinta (`MODIFICADORES_JERARQUICOS_NO_CATALOGADOS`, ej. "vice-", "encargado de-"). El caso principal (Director vs. Subdirector) ya lo resuelve el catálogo directamente.
- **Idioma y resolución del OCR** (`OCR_IDIOMA`, `OCR_DPI`).
- **Catálogo oficial de niveles por tipo de puesto** (`CATALOGO_NIVELES_POR_TIPO_PUESTO`): mapea el "nombre de pila" de un puesto (ej. "Dirección General", "J.U.D.") a su(s) nivel(es) oficial(es) válido(s). Es la ÚNICA fuente de verdad para niveles — se usa para: (1) separar tipo de puesto y nombre específico, (2) validar el nivel encontrado contra el catálogo, (3) evitar que números que son parte del nombre del puesto (ej. "Zona 1", "Zona 2") se confundan con el nivel durante la extracción del organigrama. Si tu catálogo tiene categorías distintas a las de CDMX, edita este diccionario. Usa `EXCEPCIONES_CATALOGO_NIVELES` para excluir títulos que "heredan" una palabra de la jerarquía pero no corresponden a ese nivel (ej. "Secretaría Particular").
- **Ollama (segunda opinión de IA, opcional y deshabilitada por defecto)**: para activarla, instala [Ollama](https://ollama.com), corre `ollama pull qwen2.5:7b-instruct`, deja el servidor corriendo (`ollama serve`, normalmente automático), instala la dependencia opcional `pip install requests`, y cambia en `config.py`:
  ```python
  OLLAMA_ENABLED = True
  ```
  Solo se consulta para el pequeño número de casos que el sistema determinista deja en "Requiere revisión" — nunca para el resto. Se puede ajustar `OLLAMA_MODEL`, `OLLAMA_CONFIANZA_MINIMA_PARA_ACEPTAR` (qué tan seguro debe estar el modelo para aceptar una coincidencia sin revisión manual) y `OLLAMA_TIMEOUT_SEGUNDOS` en el mismo archivo.

---

## 7. Pruebas

```bash
pip install pytest
pytest tests/ -v
```

Incluye pruebas unitarias (normalización, fuzzy matching) y de integración (comparador de 3 fuentes con datos sintéticos, y un caso end-to-end completo usando los archivos de ejemplo en `tests/fixtures/`).

Para regenerar los archivos de ejemplo (requiere LibreOffice instalado para la conversión Word→PDF y `reportlab` para el organigrama sintético), hay scripts de referencia en el historial de desarrollo; los fixtures ya generados están incluidos en `tests/fixtures/`.

---

## 8. Limitaciones conocidas y recomendaciones de mantenimiento

- **OCR nunca será 100% preciso.** Cualquier dato extraído por OCR se marca con `metodo_extraccion = "OCR"` y una confianza reducida (0.6 por defecto) — revisa esas filas con más cuidado en el reporte.
- **El organigrama sigue siendo la fuente más sensible al diseño de origen.** El método principal usa los rectángulos vectoriales reales de cada caja (`ORGANIGRAMA_USAR_CAJAS_VECTORIALES = True`), validado contra un organigrama real de gobierno. Si un organigrama no expone bordes vectoriales (por ejemplo, si Visio lo exportó como imagen dentro del PDF), el sistema cae automáticamente al método de agrupación por cercanía; en ese caso ajusta `ORGANIGRAMA_AGRUPACION_DISTANCIA_RELATIVA` en `config.py` antes de tocar el código. Si aparecen bloques de metadatos (ANEXO, OFICIO, FOLIO, etc.) mezclados con los puestos, agrega el patrón correspondiente a `ORGANIGRAMA_TEXTO_IGNORAR_PATRONES`.
- **Un solo umbral fuzzy no es infalible.** Si notas falsos positivos o negativos frecuentes, ajusta `FUZZY_UMBRAL_ALTA_CONFIANZA` / `FUZZY_UMBRAL_REVISION_MIN`, o agrega nuevos prefijos a `PREFIJOS_JERARQUICOS`.
- **Todo el procesamiento es local.** No se envía ningún documento a servicios externos; no hay llamadas a APIs de terceros en ningún módulo.
- Los logs de cada ejecución quedan en `logs/proceso.log` para depuración técnica.

---

## 9. Diagnóstico: falsos "puesto faltante" (corregido)

Durante una auditoría del comparador se detectaron y corrigieron dos causas raíz que generaban falsos "Puesto faltante" incluso cuando el puesto sí existía en Word/Organigrama:

**Causa 1 — Abreviaturas no se expandían antes de comparar.**
"J.U.D. de X" vs "Jefatura de Unidad Departamental de X" (el mismo puesto) daba una similitud de texto de solo 64% — muy por debajo del umbral de revisión (80%) — porque la comparación se hacía sobre texto crudo sin reconocer que son sinónimos administrativos. Se agregó `config.ABREVIATURAS_PUESTO` con un diccionario de abreviaturas comunes (J.U.D., L.C.P., Dir., Subdir., Depto., etc.) que se expanden **solo** para construir la clave de comparación entre fuentes (`normalization/normalizer.py: normalizar_para_comparacion()`); el texto original que ve el usuario nunca se modifica.

**Causa 2 — Asignación voraz sin reconsiderar (bug de mayor impacto).**
El algoritmo anterior recorría las claves de Excel en el orden en que aparecían y les asignaba pareja de inmediato. Si una clave con un sufijo (ej. "...Obras Públicas A") se procesaba *antes* que la clave "base" ("...Obras Públicas"), y ambas tenían cierta similitud con la única coincidencia disponible en Word, la primera "se quedaba" con esa pareja vía fuzzy matching — dejando a la clave que en realidad tenía una coincidencia **exacta** disponible sin nada, reportada como falso faltante. Se reescribió el emparejamiento en `comparison/comparator.py` (`_emparejar_conjunto`) para que sea **global y no dependa del orden de inserción**: se generan todos los pares candidatos posibles, se ordenan por calidad de coincidencia (las coincidencias exactas siempre primero, sin importar el orden de aparición) y se asignan de mayor a menor puntaje. Se verificó explícitamente que el resultado no cambia si se invierte el orden de las filas del Excel (`tests/test_diagnostico_falsos_faltantes.py::test_emparejamiento_global_no_depende_del_orden_de_insercion`).

**Lo que NO se tocó:** los umbrales de similitud (93% / 80%) ya clasificaban correctamente los ejemplos de calibración probados (incluyendo diferencias de acento, mayúsculas, saltos de línea, palabras faltantes, y el caso "Director" vs. "Subdirector", que debe seguir sin coincidir). El problema nunca estuvo en los umbrales.

**Mejora adicional (no relacionada con el bug, pero solicitada):** se agregó un pequeño bono de confianza (+4, tope 100) cuando dos puestos comparten el mismo "tipo de puesto" según el catálogo oficial (Dirección, Subdirección, J.U.D., etc.), para que títulos largos y compuestos con palabras descriptivas ligeramente distintas no se descarten solo por diluirse la similitud de texto total. Se probó que esto no relaja la protección contra falsos positivos: dos Subdirecciones de áreas genuinamente distintas (ej. Finanzas vs. Recursos Humanos) siguen clasificándose como "sin coincidencia" incluso con el bono aplicado.

### Nueva lógica de comparación, en breve

1. Cada fuente se agrupa dos veces: por texto normalizado "crudo" (para detectar duplicados dentro de la misma fuente) y por una **clave de comparación** con abreviaturas expandidas (para emparejar entre fuentes).
2. Para Excel↔Word y Excel↔Organigrama, se generan TODOS los pares candidatos (exactos y aproximados), se ordenan por calidad, y se asignan de mayor a menor — nunca en el orden en que aparecen las filas.
3. Las claves de Word/Organigrama que quedan sin pareja en Excel se comparan entre sí con el mismo algoritmo, para saber si coinciden entre ellas (aunque falten en Excel) y reportarse como "Puesto adicional" de forma más informativa.
4. Cada resultado lleva: texto original de cada fuente, ubicación exacta, nivel de coincidencia de nombre (Exacta / Normalizada / Posible coincidencia / Requiere revisión), porcentaje de confianza, y un motivo en texto libre — todo exportado en el reporte Excel.

### Pruebas de regresión agregadas

`tests/test_diagnostico_falsos_faltantes.py` reproduce ambas causas raíz exactamente como se diagnosticaron (incluyendo una prueba que invierte el orden de las filas del Excel para confirmar que el resultado no cambia) y añade los casos textuales exactos proporcionados durante el diagnóstico: puesto dividido en dos líneas, diferencia por una palabra faltante (debe dar "posible coincidencia" ~96%, no faltante), abreviaturas J.U.D./L.C.P., y un control negativo (un puesto que genuinamente no existe en otra fuente debe seguir marcado como faltante). Los 43 tests del proyecto pasan.

### Mejoras futuras (no implementadas, fuera del alcance de esta corrección)

- **Aprovechar la jerarquía del organigrama**: actualmente solo se comparan nombres y niveles; el organigrama también contiene relaciones jefe→subordinado que podrían usarse para desambiguar puestos con el mismo nombre en áreas distintas (ej. dos "Subdirección de Recursos Humanos" en dependencias diferentes), evolucionando de una comparación de texto a una validación estructural real.
- **Matching por bloqueo/índice** si el catálogo de puestos crece a varios miles de registros: el emparejamiento global actual es O(n×m) en el peor caso (todas las claves de Excel contra todas las de Word/Organigrama cuando no hay coincidencia exacta), adecuado para cientos o pocos miles de puestos, pero se beneficiaría de un índice por palabra clave si la organización crece mucho más.

## 10. Segunda revisión: extracción de Word y equivalencias institucionales

Una segunda auditoría, enfocada en cómo se extraen los puestos del documento Word y en el manejo de abreviaturas institucionales, encontró y corrigió tres bugs adicionales de extracción, y añadió una capa explícita de "equivalencias institucionales" al comparador.

### A. Diagnóstico

**Bug 1 — Encabezado "DENOMINACIÓN" solo (sin "DEL PUESTO") no se reconocía.** Las tablas de Word con esa variante de encabezado (muy común) se descartaban por completo: 0 de N filas extraídas, sin ningún aviso. Es la explicación más probable detrás del síntoma "Word: 1" — si la tabla real usa ese encabezado, prácticamente todo se pierde.

**Bug 2 — Tablas sin bordes visibles en el PDF de Word.** `pdfplumber`, con su detección de tablas por defecto (basada en líneas), regresa **cero tablas** cuando el documento usa una tabla sin bordes dibujados (estilo muy común en documentos de gobierno). Antes de esta corrección, esto también causaba una pérdida silenciosa del 100% del contenido de esa página.

**Bug 3 (relacionado) — Tablas que continúan en otra página sin repetir encabezado.** Como cada tabla necesitaba su propio encabezado reconocible, una continuación sin encabezado repetido se descartaba igual que el Bug 1.

**Causa por qué no se detectaron antes:** los tres bugs son de "extracción cero silenciosa" — no lanzan ningún error, simplemente producen 0 registros para esa tabla/página, por lo que el resto del pipeline (normalización, comparación, reporte) funciona con normalidad pero sobre datos incompletos, generando falsos "Puesto faltante" para cada fila perdida.

### B. Cambios realizados

| Archivo | Cambio |
|---|---|
| `config.py` | Se agregó `"denominacion"` (sin "del puesto") a `WORD_HEADERS_PUESTO`; se agregó `WORD_HEADERS_CANTIDAD`; se agregaron patrones de encabezados repetidos a `WORD_FILAS_IGNORAR_PATRONES`; se documentó que los candidatos de encabezado deben escribirse SIN acentos (bug de comparación insensible a acentos corregido de forma sistémica). |
| `extractors/word_extractor.py` | `_encontrar_indices_columnas` ahora también detecta la columna "Cantidad". Nueva función `_extraer_por_patron_de_linea` (respaldo cuando `pdfplumber` no detecta ninguna tabla en una página: analiza cada línea de texto buscando la forma "cantidad puesto nivel" o "puesto nivel"). Este mismo respaldo resuelve de forma natural la continuación de tablas entre páginas, porque no depende de encontrar un encabezado. |
| `models/models.py` | Nuevo campo `PuestoRecord.cantidad`; nuevo `NivelComparacion.EQUIVALENCIA_INSTITUCIONAL`; nuevo `TipoInconsistencia.COINCIDE_EQUIVALENCIA`; nuevos campos `ComparisonResult.equivalencia_aplicada` y `.puesto_canonico`. |
| `normalization/normalizer.py` | Nuevas funciones `detectar_abreviaturas_en_texto()` (para auditoría) y `detectar_posible_abreviatura_no_reconocida()` (advertencia conservadora, nunca asume significados). |
| `comparison/comparator.py` | El emparejamiento ahora distingue explícitamente **Exacta > Normalizada > Equivalencia institucional > Fuzzy alta > Requiere revisión**, y genera una nota de auditoría (ej. `"LCP → lider coordinador de proyectos"`) cuando una coincidencia dependió de una abreviatura. |
| `reports/excel_report.py` | Nuevas columnas "Puesto canónico" y "Equivalencia institucional aplicada"; la hoja Resumen ahora incluye un **desglose por fuente** (Extraídos / Válidos / Coincidencias / Posibles coincidencias / Faltantes) en vez de una sola cifra ambigua. |

**Nada existente se eliminó.** El catálogo de abreviaturas (`config.ABREVIATURAS_PUESTO`) y la función `normalizar_para_comparacion()` ya existían de una revisión anterior; esta ronda los hizo más explícitos en el resultado (antes, una coincidencia por abreviatura se reportaba igual que cualquier otra "coincide después de normalización", sin indicar cuál abreviatura se usó).

### C. Nueva lógica (extracción → comparación)

```
EXCEL ──┐
         │  normalizar_puesto()
WORD ────┼──────────────────────► puesto_normalizado (conserva texto original)
         │  (tablas: por encabezado O por patrón de línea de respaldo)
ORGANIG.─┘

puesto_normalizado ──► normalizar_para_comparacion() ──► clave de comparación
                        (expande abreviaturas del catálogo institucional)

Excel × Word, Excel × Organigrama:
  emparejamiento GLOBAL por clave de comparación (exacto siempre gana;
  si no hay exacto, fuzzy con reglas — nunca voraz por orden de fila)

Por cada pareja encontrada:
  ¿texto original idéntico?            → Exacta            (100%)
  ¿mismo texto normalizado?            → Normalizada        (100%)
  ¿coincide solo tras expandir abrev.? → Equiv. institucional (100%, con nota de auditoría)
  ¿similitud alta sin ser exacta?      → Posible coincidencia (93-99%)
  ¿similitud media?                    → Requiere revisión    (80-92%)
  ¿nada de lo anterior?                → Puesto faltante / adicional
```

### D. Pruebas realizadas

- `tests/test_word_tablas.py` (5 pruebas): encabezado "DENOMINACIÓN" solo, columna CANTIDAD, tabla sin bordes recuperada por patrón de línea (con LibreOffice generando el PDF real), fila de encabezado repetida no se cuenta como puesto.
- `tests/test_equivalencias_institucionales.py` (11 pruebas): los 5 casos obligatorios exactos que diste (L.C.P./J.U.D. en las 3 fuentes, puesto compuesto, puesto realmente distinto, similar-no-equivalente), bidireccionalidad de la equivalencia, abreviatura no reconocida marcada como advertencia (no inventada), y verificación de que la nota de auditoría queda registrada.
- Prueba de escala real: se tomó el organigrama real de 284 puestos, se reemplazaron todas las abreviaturas J.U.D./L.C.P. por su nombre completo en un Excel sintético, y se comparó contra el organigrama abreviado original — **0 falsos faltantes**.
- Suite completa: **59/59 pruebas pasan.**

### E. Mejoras futuras (no implementadas)

- **Detección automática de nuevas abreviaturas recurrentes**: actualmente `detectar_posible_abreviatura_no_reconocida()` solo evalúa el primer token de cada puesto; podría ampliarse a un reporte agregado ("estas 5 abreviaturas no reconocidas aparecen X veces cada una") para facilitar decidir cuáles agregar al catálogo.
- **Aprovechar jerarquía del organigrama para desambiguar duplicados por área** (mencionado también en la primera revisión): sigue siendo la mejora estructural más grande pendiente, fuera del alcance de esta corrección de extracción/equivalencias.
- **Resumen por página del Word**: se implementó el desglose por fuente; el desglose adicional por página específica del Word no se implementó por no ser crítico para el problema de fondo (falsos faltantes) — se puede agregar reutilizando el campo `ubicacion.pagina` ya presente en cada registro si se necesita más adelante.

## 11. Tercera revisión: refactorización estructural, catálogo único y Ollama opcional

Una tercera auditoría, con instrucción explícita de "no agregar más if/else sino refactorizar", encontró y eliminó una duplicación real de lógica, separó formalmente TIPO DE PUESTO + NOMBRE ESPECÍFICO, y evaluó (con evidencia, antes de implementar) si conviene integrar Ollama como segunda opinión semántica.

### A. Diagnóstico

Se auditó todo el proyecto buscando: valores hardcodeados, catálogos duplicados, lógica repetida entre fuentes, y reglas específicas por puesto/dependencia.

**Hallazgo principal — lógica duplicada real:** existían **dos sistemas paralelos** resolviendo "¿son puestos de jerarquía distinta?": `config.PREFIJOS_JERARQUICOS` (lista manual de palabras: "sub", "vice", "adjunto a"...) en `matcher.py`, y `identificar_categoria_puesto()` (basado en el catálogo oficial) en `catalogo_niveles.py`, sin conexión entre ambos. Exactamente el tipo de duplicación que pediste auditar.

**Hallazgo secundario — comparación por texto completo diluye diferencias reales:** al expandir abreviaturas (J.U.D. → "Jefatura de Unidad Departamental") antes de comparar, dos J.U.D. de áreas genuinamente distintas terminaban comparándose con un prefijo larguísimo idéntico, lo que **inflaba artificialmente el score de similitud** (un caso real subió de 83% a 94.6% solo por el efecto de dilución). Esto confirma exactamente el punto §17 de tu especificación: hay que comparar por **componentes** (tipo + nombre específico), no por cadena completa.

**Hallazgo terciario — sufijos distintivos ("A"/"B") se fusionaban al 100%:** oficinas idénticas salvo por un sufijo de una letra (muy común en la estructura real: Dirección de Construcción "A"/"B"/"C"/"D") estaban recibiendo 100% de confianza de coincidencia por el efecto combinado de un solo carácter de diferencia en texto largo + el bono de "mismo tipo".

Ningún valor hardcodeado de puesto o dependencia específica encontrado en el código de producción (ya se había limpiado en revisiones anteriores); `config.CATALOGO_NIVELES_POR_TIPO_PUESTO` ya era la única fuente de verdad para niveles.

### B. Cambios realizados

| Archivo | Cambio |
|---|---|
| `comparison/catalogo_niveles.py` | `identificar_categoria_puesto()` ahora **canoniza** alias (J.U.D./JUD y L.C.P./LCP resuelven al mismo tipo, sin importar cuál aparezca en el texto). Nueva función `separar_tipo_y_nombre_especifico()`: separa cualquier puesto en tipo/nombre específico/niveles del catálogo. Nueva `enriquecer_con_catalogo()`: puebla estos campos en cada `PuestoRecord` tras la extracción. |
| `config.py` | `PREFIJOS_JERARQUICOS` eliminado; reemplazado por `MODIFICADORES_JERARQUICOS_NO_CATALOGADOS` (lista mínima, solo para modificadores que NO son tipos oficiales del catálogo — el caso principal, Director vs. Subdirector, ahora lo resuelve el catálogo directamente). Nueva sección `OLLAMA_*` (deshabilitado por defecto). |
| `comparison/matcher.py` | La señal de "jerarquía distinta" ahora combina: tipo del catálogo (con alias canonizados) + modificadores residuales + sufijos distintivos de una letra (nuevo). Nueva función `evaluar_coincidencia_por_componentes()`: compara solo el nombre específico cuando ambos puestos comparten tipo reconocido, evitando la dilución por prefijo largo. |
| `comparison/comparator.py` | Usa `evaluar_coincidencia_por_componentes()` en vez de comparación de texto completo. Nuevo campo `metodo_coincidencia` por resultado (Exacta/Normalización/Equivalencia/Fuzzy/IA/Revisión manual, §41). Nueva función `aplicar_segunda_opinion_ollama()` (post-procesamiento opcional). |
| `models/models.py` | Nuevos: `EstadoNivel` (válido/fuera de catálogo/no encontrado/tipo no reconocido), `MetodoCoincidencia`, campos `tipo_puesto`, `tipo_puesto_display`, `nombre_especifico`, `niveles_catalogo`, `estado_nivel` en `PuestoRecord`; `metodo_coincidencia`, `ia_consultada`, `ia_explicacion` en `ComparisonResult`. |
| `comparison/ollama_client.py` (nuevo) | Cliente HTTP hacia un servidor Ollama **local**, con caché en disco, validación estricta de esquema JSON, y degradación segura (si Ollama no responde o el JSON es inválido, el caso simplemente se queda en revisión manual — nunca se inventa una coincidencia). |
| `pipeline.py` | Llama a `enriquecer_con_catalogo()` tras la extracción y a `aplicar_segunda_opinion_ollama()` tras la comparación. |
| `reports/excel_report.py` | Nuevas columnas: Tipo de puesto, Nombre específico, Niveles según catálogo, Estado de nivel (por fuente), Método de coincidencia. |
| `requirements.txt` | `requests` agregado como dependencia **opcional** (solo se usa si `OLLAMA_ENABLED=True`). |

**Nada se eliminó sin justificar.** El catálogo, la extracción de Excel/Word/Organigrama, y el pipeline de comparación de 3 fuentes se mantuvieron intactos; los cambios fueron quirúrgicos sobre la lógica de matching y la capa de enriquecimiento.

### C. Nueva lógica (extracción → tipo/nombre específico → comparación → confianza)

```
EXTRACCIÓN (Excel / Word / Organigrama)
        │
NORMALIZACIÓN (normalizar_puesto — sin tocar el texto original)
        │
CATÁLOGO DE config.py (enriquecer_con_catalogo):
  tipo_puesto (canónico) + nombre_especifico + niveles_catalogo + estado_nivel
        │
MATCHING ENTRE FUENTES (emparejamiento global, no voraz):
  ¿clave exacta o normalizada?         → Exacta / Normalización       (100%)
  ¿coincide solo tras expandir abrev.? → Equivalencia institucional   (100%)
  ¿mismo tipo de catálogo?             → comparar SOLO nombre específico
  ¿tipos distintos o sin catálogo?     → comparar texto completo (respaldo)
        │
  ¿similitud alta (≥93)?               → Posible coincidencia
  ¿similitud media (80-92)?            → Requiere revisión
        │                                      │
        │                              ¿OLLAMA_ENABLED?
        │                                 NO         SÍ
        │                                 │          │
        │                             queda en   segunda opinión
        │                             revisión    (JSON validado,
        │                                          nunca decide niveles)
        │                                              │
        │                                    ¿confianza≥90% Y sin
        │                                     pedir revisión humana?
        │                                         SÍ        NO
        │                                         │         │
        │                                  Coincide por IA  sigue en revisión
        ▼
   RESULTADO + método de coincidencia + confianza + trazabilidad completa
```

### D. Pruebas realizadas

- `tests/test_tipo_nombre_especifico.py` (12 pruebas): separación tipo/nombre específico con los ejemplos exactos del prompt maestro (§47-49), protección de sufijos distintivos "A"/"B", validación de niveles (§49: JUD+25→válido, JUD+40→inválido, etc.), nivel no encontrado nunca se asume.
- `tests/test_ollama.py` (11 pruebas, con servidor Ollama **simulado** vía mock — no requiere Ollama instalado): confirma coincidencia ambigua real con alta confianza, nunca inventa coincidencia con baja confianza o si el propio modelo pide revisión humana, manejo de errores (timeout, JSON inválido, esquema incompleto) siempre degrada a revisión manual, caché evita consultas repetidas, y el sistema completo funciona igual con `OLLAMA_ENABLED=False`.
- Suite completa: **82/82 pruebas pasan.**
- Prueba de escala real: organigrama de 284 puestos + Excel sintético con abreviaturas forzadas a su forma completa → **0 falsos faltantes**, análisis completo en **1.3 segundos**.
- Medición de tasa de ambigüedad real (§54): con variaciones realistas de escritura, **0% de casos** caen en "Requiere revisión" — el sistema determinista resuelve la gran mayoría. Se identificaron manualmente 2 pares genuinamente ambiguos (diferencias semánticas reales, no de formato) para validar el flujo de Ollama.

### E. Evaluación de Ollama (§53) y por qué se implementó como opcional

**Conclusión de la evaluación:** sí aporta valor, pero de forma muy acotada. La gran mayoría de los falsos faltantes reales tenían causas deterministas resolubles (abreviaturas, encabezados de tabla, bordes de PDF, asignación voraz) — todas corregidas en las tres revisiones. Lo que queda tras esas correcciones es un porcentaje pequeño de casos con ambigüedad **semántica genuina** (ej. "JUD de Seguimiento y Evaluación de Proyectos" vs "JUD de Seguimiento de Proyectos", 80.6%) donde ni el catálogo ni el fuzzy matching pueden decidir con certeza si son la misma oficina — exactamente el tipo de caso para el que una segunda opinión de un modelo de lenguaje tiene sentido.

**Por qué quedó deshabilitada por defecto (`OLLAMA_ENABLED = False`):** requiere un servidor Ollama corriendo en tu máquina, que no pude instalar ni probar en vivo desde este entorno de desarrollo. La integración se implementó y probó exhaustivamente con un servidor **simulado**, validando toda la lógica (payload, esquema de respuesta, caché, manejo de errores) — pero la prueba con el modelo real (`qwen2.5:7b-instruct`) queda pendiente de que la actives en tu máquina. Instrucciones de activación en la sección 6 (`OLLAMA_ENABLED = True` en `config.py`, y tener Ollama corriendo con `ollama pull qwen2.5:7b-instruct`).

### F. Problemas que todavía requieren revisión humana

- Los pares genuinamente ambiguos por diferencia semántica real (no de formato) seguirán marcados "Requiere revisión" hasta que actives Ollama o los revises manualmente — es el comportamiento correcto por diseño (§14 del ajuste de equivalencias: mejor revisión manual que una coincidencia inventada).
- Puestos con nombres no estándar que no corresponden a ningún tipo del catálogo (ej. "Asesor A", "Secretaría Particular") quedan con `tipo_puesto=None` y no se valida su nivel contra el catálogo — es esperado, no todos los puestos siguen la nomenclatura estándar de niveles.

## 12. Cuarta revisión: modos de análisis y acceso local/remoto

### A. Cambios realizados

| Archivo | Cambio |
|---|---|
| `pipeline.py` | Nuevo `ModoAnalisis` (enum: `COMPLETO` / `EXCEL_ORGANIGRAMA`). `ejecutar_analisis()` acepta `modo` y `ruta_word` ahora es opcional (`None` en modo `EXCEL_ORGANIGRAMA`, Word ni se extrae). |
| `comparison/comparator.py` | Nuevo parámetro `incluir_word` en `comparar_fuentes()`. **Bug corregido**: sin este parámetro, un puesto que sí coincidía entre Excel y Organigrama se reportaba falsamente como "faltante" solo porque Word (que no participaba en el análisis) aparecía como "no encontrado". |
| `reports/excel_report.py` | Reescrito para adaptar columnas y resumen al modo (Word se omite por completo, no solo se deja vacío). Las columnas de ubicación técnica (página/fila/columna/tabla) se eliminaron del reporte en ambos modos — esa información se conserva internamente en `PuestoRecord.ubicacion` para depuración vía logs. |
| `ui/app.py` | Selector de modo en la barra lateral; el campo de Word se oculta automáticamente en modo Excel vs Organigrama. Nueva pantalla de acceso con contraseña opcional (`config.APP_PASSWORD`). Limpieza de archivos temporales entre ejecuciones. |
| `main.py` | Nuevo flag `--modo {completo,excel_organigrama}`; `--word` ahora opcional. |
| `config.py` | Nuevo `APP_PASSWORD` (se lee de la variable de entorno `VALIDADOR_PASSWORD`). |
| `.streamlit/config.toml` (nuevo) | Configura Streamlit para escuchar en toda la red (`0.0.0.0`), no solo en `localhost`. |
| `start_server.bat` / `start_server.sh` (nuevos) | Scripts de arranque con puerto y contraseña configurables por variable de entorno, e impresión automática de la IP local para compartir. |

### B. Por qué Tailscale para acceso remoto

Se evaluaron Tailscale, ZeroTier y Cloudflare Tunnel (las tres opciones que pediste comparar). Tailscale se documentó como la recomendación principal porque: no requiere abrir ningún puerto en el router (cumple la restricción de tu red de trabajo), funciona transparentemente detrás de NAT/firewall corporativo, tiene soporte nativo y sencillo para Windows, y el control de acceso es por cuenta de usuario (revocar acceso = quitar a la persona de tu cuenta, sin tocar configuración de red). ZeroTier es una alternativa equivalente si prefieres esa herramienta; Cloudflare Tunnel es la opción a considerar si en el futuro necesitas un link público en vez de una red privada cerrada.

### C. Pruebas realizadas

- `tests/test_modos_analisis.py` (8 pruebas): confirma que Word no participa en absoluto en modo `EXCEL_ORGANIGRAMA` (ni en la comparación, ni en el reporte, ni en el resumen), que el modo completo sigue funcionando exactamente igual que antes, que las columnas de ubicación nunca aparecen en el reporte en ningún modo, y que J.U.D./L.C.P. se siguen normalizando igual en ambos modos.
- `tests/test_ui_app.py` (3 pruebas, con `streamlit.testing.v1.AppTest` — renderiza la app en memoria sin necesitar un servidor real): confirma que la pantalla de contraseña efectivamente bloquea el acceso cuando está configurada, que sin contraseña se accede directo, y que el selector de modo está presente con las dos opciones esperadas.
- Se verificó manualmente que `.streamlit/config.toml` hace que Streamlit escuche en `0.0.0.0` sin necesidad de pasar flags, y que `start_server.sh` respeta un puerto personalizado vía variable de entorno.
- Suite completa: **93/93 pruebas pasan.**

## 13. Privacidad

Todo el análisis corre localmente en tu máquina. Los archivos temporales que crea la interfaz de Streamlit al subir documentos se guardan en el directorio temporal del sistema operativo y no se copian a ningún otro lugar del proyecto.
