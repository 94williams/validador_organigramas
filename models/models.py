"""
Modelos de datos centrales del proyecto.

Estos dataclasses son el "contrato" que usan todos los módulos:
extractores -> PuestoRecord
comparador  -> ComparisonResult
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Fuente(str, Enum):
    EXCEL = "Excel"
    WORD = "Word"
    ORGANIGRAMA = "Organigrama"


class MetodoExtraccion(str, Enum):
    TEXTO_DIRECTO = "texto_directo"
    OCR = "OCR"
    CELDA_EXCEL = "celda_excel"
    DOCX_NATIVO = "docx_nativo"
    DESCONOCIDO = "desconocido"


class NivelComparacion(str, Enum):
    EXACTA = "Exacta"
    NORMALIZADA = "Coincide después de normalización"
    EQUIVALENCIA_INSTITUCIONAL = "Coincidencia mediante equivalencia institucional"
    FUZZY_ALTA = "Posible coincidencia (alta confianza)"
    FUZZY_REVISION = "Requiere revisión"
    SIN_COINCIDENCIA = "Sin coincidencia"
    NO_APLICA = "No aplica (fuente faltante)"


class EstadoNivel(str, Enum):
    """Clasificación formal del nivel de un registro contra el catálogo oficial."""
    VALIDO = "Nivel válido según catálogo"
    FUERA_DE_CATALOGO = "Nivel fuera de catálogo"
    NO_ENCONTRADO = "Nivel no encontrado en el documento"
    TIPO_NO_RECONOCIDO = "Tipo de puesto no reconocido (no se puede validar)"


class MetodoCoincidencia(str, Enum):
    """Cómo se determinó que dos registros son el mismo puesto (para auditoría)."""
    EXACTA = "Exacta"
    NORMALIZACION = "Normalización"
    EQUIVALENCIA_INSTITUCIONAL = "Abreviatura / equivalencia institucional"
    FUZZY = "Coincidencia aproximada (fuzzy)"
    IA = "Segunda opinión (IA)"
    REVISION_MANUAL = "Revisión manual"
    NO_APLICA = "No aplica"


class TipoInconsistencia(str, Enum):
    OK = "OK"
    COINCIDE_NORMALIZADO = "Coincide después de normalización"
    COINCIDE_EQUIVALENCIA = "Coincidencia mediante equivalencia institucional"
    DIFERENCIA_FORMATO = "Diferencia de formato"
    POSIBLE_COINCIDENCIA = "Posible coincidencia"
    NIVEL_INCONSISTENTE = "Nivel inconsistente"
    NIVEL_FALTANTE = "Nivel faltante"
    NIVEL_FORMATO_INVALIDO = "Nivel con formato no reconocido"
    PUESTO_FALTANTE = "Puesto faltante"
    PUESTO_ADICIONAL = "Puesto adicional"
    DUPLICADO = "Duplicado"
    DUPLICADO_NIVEL_DISTINTO = "Duplicado con nivel distinto"
    REQUIERE_REVISION = "Requiere revisión"
    COINCIDE_IA = "Coincidencia resuelta por IA (revisión semántica)"
    ERROR_EXTRACCION = "Error de extracción"


@dataclass
class Ubicacion:
    """Trazabilidad: dónde se encontró exactamente un dato."""
    archivo: str
    hoja: Optional[str] = None            # Excel
    fila: Optional[int] = None            # Excel / tabla Word
    columna: Optional[str] = None         # Excel
    pagina: Optional[int] = None          # PDF (Word u organigrama)
    tabla_index: Optional[int] = None     # Word
    fila_tabla: Optional[int] = None      # Word
    posicion_aprox: Optional[str] = None  # Organigrama: "x=120,y=340"
    bbox: Optional[tuple] = None          # Organigrama: bounding box del bloque

    def resumen(self) -> str:
        partes = [self.archivo]
        if self.hoja:
            partes.append(f"hoja='{self.hoja}'")
        if self.fila is not None:
            partes.append(f"fila={self.fila}")
        if self.columna:
            partes.append(f"col={self.columna}")
        if self.pagina is not None:
            partes.append(f"pág={self.pagina}")
        if self.tabla_index is not None:
            partes.append(f"tabla={self.tabla_index}")
        if self.fila_tabla is not None:
            partes.append(f"fila_tabla={self.fila_tabla}")
        if self.posicion_aprox:
            partes.append(f"pos≈{self.posicion_aprox}")
        return " | ".join(partes)


@dataclass
class PuestoRecord:
    """Un registro puesto/nivel extraído de una fuente."""
    fuente: Fuente
    puesto_original: str
    nivel_original: Optional[str]
    puesto_normalizado: str = ""
    nivel_normalizado: Optional[str] = None
    ubicacion: Optional[Ubicacion] = None
    metodo_extraccion: MetodoExtraccion = MetodoExtraccion.DESCONOCIDO
    confianza_extraccion: float = 1.0  # 1.0 = texto directo confiable; baja para OCR dudoso
    cantidad: Optional[str] = None  # columna "CANTIDAD" en tablas de Word, cuando existe
    error: Optional[str] = None

    # --- Separación tipo de puesto / nombre específico (catálogo oficial) ---
    # Se pueblan mediante comparison.catalogo_niveles.separar_tipo_y_nombre_especifico()
    # después de la extracción; quedan None si el puesto no corresponde a
    # ningún tipo del catálogo (puesto no clasificable).
    tipo_puesto: Optional[str] = None            # clave canónica, ej. "jefatura de unidad departamental"
    tipo_puesto_display: Optional[str] = None    # forma legible, ej. "Jefatura de Unidad Departamental"
    nombre_especifico: Optional[str] = None      # ej. "de apoyo en operación"
    niveles_catalogo: list = field(default_factory=list)  # niveles oficiales válidos para el tipo detectado
    estado_nivel: Optional["EstadoNivel"] = None  # válido / fuera de catálogo / no encontrado / tipo no reconocido

    @property
    def valido(self) -> bool:
        return self.error is None and bool(self.puesto_original and self.puesto_original.strip())


@dataclass
class ComparisonResult:
    """Resultado de comparar un puesto a través de las 3 fuentes."""
    puesto_clave_normalizada: str
    excel: Optional[PuestoRecord] = None
    word: Optional[PuestoRecord] = None
    organigrama: Optional[PuestoRecord] = None
    tipo_inconsistencia: TipoInconsistencia = TipoInconsistencia.OK
    detalle: str = ""
    nivel_comparacion_nombre: NivelComparacion = NivelComparacion.EXACTA
    confianza_match: float = 100.0
    es_duplicado: bool = False
    ids_relacionados: list = field(default_factory=list)  # para agrupar duplicados
    advertencia_catalogo: str = ""  # validación informativa contra catálogo oficial de niveles
    equivalencia_aplicada: str = ""  # ej. "J.U.D. → jefatura de unidad departamental"
    puesto_canonico: str = ""  # clave de comparación con abreviaturas expandidas
    metodo_coincidencia: "MetodoCoincidencia" = None  # cómo se determinó la coincidencia (auditoría, §41)
    ia_consultada: bool = False
    ia_explicacion: str = ""
