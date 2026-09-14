"""
Configuración central. Ajusta aquí los parámetros del proyecto
sin tocar la lógica de los módulos.
"""

# ---------------------------------------------------------------------------
# EXCEL: nombres de encabezado esperados (se busca por coincidencia parcial,
# insensible a mayúsculas/acentos). Si no se encuentra ningún encabezado
# reconocible, se usa el fallback de columnas fijas J/K.
# ---------------------------------------------------------------------------
# Nota: el orden de evaluación importa. "nivel" se revisa antes que "puesto"
# en el extractor porque encabezados como "Nivel del puesto" contienen la
# palabra "puesto" y se clasificarían mal si se revisara al revés.
# IMPORTANTE: estos candidatos se comparan usando texto YA normalizado
# (sin acentos), así que aquí deben escribirse SIN acentos — de lo
# contrario nunca coinciden contra el encabezado normalizado (bug real
# detectado: "denominación del puesto" con acento nunca hacía match).
EXCEL_HEADERS_PUESTO = [
    "puesto",
    "nombre del puesto",
    "nombre de puesto",
    "denominacion del puesto",
    "denominacion",
    "nombre del cargo",
    "denominacion del cargo",
    "cargo",
    "titulo del puesto",
    "estructura propuesta",
]
EXCEL_HEADERS_NIVEL = [
    "nivel",
    "nivel del puesto",
    "nivel de puesto",
    "nivel salarial",
    "nivel orgánico",
    "nivel de cargo",
]
EXCEL_FALLBACK_COL_PUESTO = "J"
EXCEL_FALLBACK_COL_NIVEL = "K"
EXCEL_FILA_INICIO_BUSQUEDA_HEADER = 1
EXCEL_MAX_FILAS_BUSQUEDA_HEADER = 30  # revisa más filas para aceptar encabezados más abajo en la hoja

# ---------------------------------------------------------------------------
# WORD: encabezados de columna de tabla que se reconocen como puesto/nivel.
# Mismo cuidado que en EXCEL_HEADERS_*: escribir SIN acentos (se comparan
# contra texto ya normalizado). Se incluye "denominacion" SOLA (sin "del
# puesto") porque es una variante real muy común en documentos de gobierno
# y, antes de esta corrección, causaba que la tabla completa se descartara.
# ---------------------------------------------------------------------------
WORD_HEADERS_PUESTO = [
    "puesto", "nombre del puesto", "cargo", "denominacion del puesto", "denominacion",
]
WORD_HEADERS_NIVEL = ["nivel", "nivel del puesto", "nivel de puesto"]
WORD_HEADERS_CANTIDAD = ["cantidad", "num", "no", "numero", "plazas"]

# Filas de tabla a ignorar (texto administrativo / no es un puesto real).
# Incluye variantes de encabezados repetidos (comunes cuando una tabla
# continúa en otra página y Word repite la fila de encabezado).
WORD_FILAS_IGNORAR_PATRONES = [
    r"^p[aá]gina\s*\d+", r"^total\s*:?", r"^continua\b", r"^\s*$",
    r"^cantidad$", r"^denominaci", r"^nivel$", r"^estructura\b", r"^puesto$",
]

# ---------------------------------------------------------------------------
# ORGANIGRAMA (PDF): patrones para identificar el nivel dentro de un bloque
# de texto que contiene tanto el nombre del puesto como el nivel.
# ---------------------------------------------------------------------------
NIVEL_PATTERNS = [
    r"nivel\s*[:\-]?\s*(\d{1,3})",
    r"\bn[ivl]*[\.\-]?\s*(\d{1,3})\b",   # N-8, NVL 8, N.8
    r"\b(\d{1,3})\b",                     # último recurso: número suelto
]

# Distancia vertical máxima (proporción del alto de página) para agrupar
# bloques de texto como parte de la misma "caja" del organigrama.
# Se usa SOLO como método de respaldo cuando la página no tiene cajas
# vectoriales detectables (ver ORGANIGRAMA_USAR_CAJAS_VECTORIALES).
ORGANIGRAMA_AGRUPACION_DISTANCIA_RELATIVA = 0.03

# --- Método preferido: detección de cajas reales por sus bordes vectoriales ---
# La mayoría de los organigramas exportados de Visio dibujan cada puesto
# como un rectángulo con borde. PyMuPDF puede leer esos trazos vectoriales
# directamente, lo que da una delimitación mucho más confiable que agrupar
# texto por cercanía (ver análisis: evita fusionar cajas adyacentes en
# organigramas densos con muchas columnas).
ORGANIGRAMA_USAR_CAJAS_VECTORIALES = True

# Tolerancia (en puntos PDF) para considerar dos rectángulos como "el mismo"
# (Visio suele dibujar el borde y el relleno de una caja como dos trazos
# casi idénticos, con 1-2pt de diferencia).
ORGANIGRAMA_RECT_DEDUPE_TOLERANCIA = 3

# Un rectángulo se considera "caja de puesto" si su área está entre estos
# múltiplos de la mediana de áreas de la página. Esto filtra automáticamente
# el borde de la página completa y paneles grandes de metadatos (mucho más
# grandes que una caja de puesto típica) sin necesitar tamaños fijos en
# puntos, que cambiarían de un organigrama a otro.
ORGANIGRAMA_AREA_RATIO_MIN = 0.2
ORGANIGRAMA_AREA_RATIO_MAX = 6.0

# Texto que debe ignorarse aunque caiga dentro de una caja detectada
# (paneles de metadatos del dictamen: "ANEXO II", "OFICIO: ...", etc.)
ORGANIGRAMA_TEXTO_IGNORAR_PATRONES = [
    r"^anexo\b", r"^organigrama$", r"^oficio\b", r"^folio\b", r"^dictamen\b",
    r"^dependencia\b", r"^unidad administrativa\b", r"^inicio de vigencia\b",
    r"^total de plazas\b", r"^d-[a-z]+-\d+",
]

# ---------------------------------------------------------------------------
# FUZZY MATCHING
# ---------------------------------------------------------------------------
FUZZY_UMBRAL_ALTA_CONFIANZA = 93      # >= esto: coincidencia automática aceptada
FUZZY_UMBRAL_REVISION_MIN = 80        # entre este y el de arriba: "requiere revisión"
# por debajo de FUZZY_UMBRAL_REVISION_MIN: se considera que no hay relación

# Modificadores genéricos que indican una jerarquía distinta pero que NO
# son "tipos de puesto" del catálogo oficial de la CDMX (por lo tanto no
# pueden resolverse vía config.CATALOGO_NIVELES_POR_TIPO_PUESTO). El caso
# más común e importante (Director vs. Subdirector) ya lo resuelve el
# catálogo directamente -ver comparison/catalogo_niveles.py-, así que esta
# lista se mantiene intencionalmente corta: es solo una red de seguridad
# adicional para palabras que modifican la jerarquía y no están en ningún
# catálogo institucional.
MODIFICADORES_JERARQUICOS_NO_CATALOGADOS = [
    "vice", "adjunto a", "encargado de", "auxiliar de", "asistente de",
]

# ---------------------------------------------------------------------------
# OCR
# ---------------------------------------------------------------------------
OCR_IDIOMA = "spa"
OCR_DPI = 300
OCR_CONFIANZA_DEFECTO = 0.6  # confianza asignada a datos que vinieron de OCR

# ---------------------------------------------------------------------------
# ABREVIATURAS: se expanden ÚNICAMENTE para efectos de comparación entre
# fuentes (nunca se modifica el texto mostrado al usuario). Esto es crítico
# porque es común que una fuente abrevie ("J.U.D.") y otra escriba el nombre
# completo ("Jefatura de Unidad Departamental"); sin esta expansión, la
# similitud de texto entre ambas cae muy por debajo del umbral de revisión
# y se reporta como un falso "puesto faltante".
# Las claves deben ser el token YA normalizado (minúsculas, sin acentos,
# sin puntuación) tal como queda tras normalizar_puesto().
# ---------------------------------------------------------------------------
ABREVIATURAS_PUESTO = {
    "jud": "jefatura de unidad departamental",
    "lcp": "lider coordinador de proyectos",
    "dir": "direccion",
    "subdir": "subdireccion",
    "depto": "departamento",
    "dpto": "departamento",
    "coord": "coordinacion",
    "gral": "general",
    "grl": "general",
    "ejec": "ejecutiva",
    "tec": "tecnica",
    "admon": "administracion",
    "rh": "recursos humanos",
    "rrhh": "recursos humanos",
}

# ---------------------------------------------------------------------------
# NIVEL: representaciones equivalentes de "nivel"
# ---------------------------------------------------------------------------
NIVEL_NORMALIZACION_PATTERNS = [
    r"nivel\s*", r"^n[\-\.]?\s*", r"nvl\.?\s*",
]

# ---------------------------------------------------------------------------
# CATÁLOGO OFICIAL DE NIVELES POR TIPO DE PUESTO (Gobierno CDMX)
# ---------------------------------------------------------------------------
# Cada clave es un "nombre de pila" del puesto ya normalizado (minúsculas,
# sin acentos); el puesto real puede continuar con más texto después
# (ej. "Dirección General" hace match con "Dirección General de
# Construcción de Obras Públicas"). Se incluyen alias de abreviaturas
# comunes en organigramas reales (J.U.D., L.C.P.).
#
# Varias categorías tienen más de un nivel válido porque el catálogo oficial
# distingue sub-niveles dentro de la misma categoría (p. ej. Dirección
# General "A" vs "B"); esto es normal y no debe reportarse como error.
CATALOGO_NIVELES_POR_TIPO_PUESTO = {
    "jefatura de gobierno": [49],
    "secretaria": [48],
    "subsecretaria": [47],
    "alcaldia": [47],
    "coordinacion general": [47, 46],
    "direccion general": [45, 44],
    "direccion ejecutiva": [43, 42],
    "direccion tecnica": [40, 39],
    "direccion": [40, 39],
    "coordinacion": [34, 32],  # 34 standalone; 32 cuando corresponde al renglón combinado "Subdirección / Coordinación"
    "subdireccion tecnica": [29],
    "subdireccion": [29, 32],
    "jefatura de unidad departamental": [27, 25],
    "jud": [27, 25],  # abreviatura muy común en organigramas reales
    "lider coordinador de proyectos": [24, 23],
    "lcp": [24, 23],  # abreviatura muy común en organigramas reales
    "enlace": [21, 20],
}

# Todos los niveles numéricos válidos según el catálogo anterior (unión).
# Se usa como lista de referencia al EXTRAER el organigrama: cuando una caja
# contiene más de un número (p. ej. "J.U.D. de Limpieza Urbana Zona 1" con
# nivel 25: el "1" es parte del nombre, no el nivel), se prioriza como nivel
# el número que sí aparece en esta lista, evitando confundir números de zona/
# turno con el nivel real. Si ninguno coincide, se usa el comportamiento
# anterior (primer número encontrado).
NIVELES_VALIDOS_CONOCIDOS = sorted({n for niveles in CATALOGO_NIVELES_POR_TIPO_PUESTO.values() for n in niveles})

# Puestos que, aunque empiecen con una palabra del catálogo, NO deben
# validarse contra él porque son excepciones conocidas (oficinas de apoyo
# con nombres que "heredan" la palabra de una jerarquía superior pero no
# corresponden a ese nivel). Ejemplo real: "Secretaría Particular" empieza
# con "Secretaría" pero es nivel 44, no 48. Agrega aquí más casos según los
# vayas encontrando en tus propios documentos.
EXCEPCIONES_CATALOGO_NIVELES = [
    "secretaria particular", "secretaria tecnica", "secretaria privada",
]

# ---------------------------------------------------------------------------
# OLLAMA (segunda opinión semántica para casos ambiguos, §29-42)
# ---------------------------------------------------------------------------
# Deshabilitado por defecto: el programa debe funcionar completo sin Ollama.
# Solo se consulta cuando el matching determinista deja un caso en la banda
# "Requiere revisión" (ver comparison/matcher.py) — nunca reemplaza al
# catálogo, la extracción, ni la comparación determinista.
OLLAMA_ENABLED = False
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "qwen2.5:7b-instruct"
OLLAMA_TIMEOUT_SEGUNDOS = 20
OLLAMA_CONFIANZA_MINIMA_PARA_ACEPTAR = 0.90  # por debajo de esto, sigue en revisión manual aunque Ollama opine "sí"
OLLAMA_CACHE_ARCHIVO = "logs/cache_ollama.json"  # se persiste entre ejecuciones

# ---------------------------------------------------------------------------
# ACCESO A LA INTERFAZ (local / red local / remoto)
# ---------------------------------------------------------------------------
# Contraseña opcional para la interfaz Streamlit. None (por defecto) = sin
# contraseña, cualquiera con el link puede entrar. Recomendado establecerla
# si la app se comparte fuera de tu máquina (red local o remota) — ver
# README, sección "Acceso local y remoto", para más contexto de seguridad.
# Se lee de la variable de entorno VALIDADOR_PASSWORD (la fijan los scripts
# start_server.bat / start_server.sh); si prefieres fijarla aquí
# directamente, reemplaza la línea de abajo por: APP_PASSWORD = "tu-clave".
# NUNCA subas una contraseña en texto plano a un repositorio público.
import os as _os
APP_PASSWORD = _os.environ.get("VALIDADOR_PASSWORD")

# ---------------------------------------------------------------------------
# RUTAS
# ---------------------------------------------------------------------------
LOG_DIR = "logs"
LOG_FILE = "proceso.log"
