"""
Cliente de Ollama: segunda opinión SEMÁNTICA para casos que el matching
determinista deja en la banda "Requiere revisión" (ver comparison/matcher.py).

Principios de diseño (§29-42 del prompt maestro):
- OPCIONAL: si Ollama no está instalado/disponible o config.OLLAMA_ENABLED
  es False, el resto del sistema sigue funcionando exactamente igual.
- NUNCA determina niveles. Solo responde "¿son el mismo puesto?" con una
  confianza; el nivel y su validación siguen viniendo exclusivamente del
  documento y de config.CATALOGO_NIVELES_POR_TIPO_PUESTO.
- Solo se le envía la información mínima relevante (nunca documentos
  completos): los nombres de puesto en cuestión, el tipo del catálogo y
  los niveles permitidos.
- Respuesta en JSON estructurado y validado; si la IA responde algo que no
  se puede interpretar como JSON válido, se descarta y el caso se queda en
  revisión manual (nunca se "inventa" una coincidencia).
- Caché en disco: una vez resuelta una comparación, no se vuelve a
  consultar (importante por el costo de inferencia en CPU).
"""
import json
import os
import sys
from typing import Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402
from utils.logger import get_logger  # noqa: E402

logger = get_logger("ollama_client")

_CACHE_MEMORIA: dict = {}
_CACHE_CARGADA = False

_PROMPT_SISTEMA = (
    "Eres un asistente especializado en estructuras organizacionales del gobierno de México. "
    "Tu única tarea es determinar si dos denominaciones de puesto se refieren al mismo puesto. "
    "Responde ÚNICAMENTE con un objeto JSON válido, sin texto adicional, exactamente con estas claves: "
    '{"es_mismo_puesto": bool, "confianza": float entre 0 y 1, '
    '"coincidencia_nombre_especifico": bool, "requiere_revision_humana": bool, "explicacion": "texto breve"}. '
    "NUNCA propongas ni corrijas niveles jerárquicos; eso no es tu tarea."
)


def _clave_cache(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def _cargar_cache() -> None:
    global _CACHE_CARGADA
    if _CACHE_CARGADA:
        return
    _CACHE_CARGADA = True
    ruta = config.OLLAMA_CACHE_ARCHIVO
    if os.path.exists(ruta):
        try:
            with open(ruta, "r", encoding="utf-8") as f:
                _CACHE_MEMORIA.update(json.load(f))
            logger.info(f"Caché de Ollama cargada: {len(_CACHE_MEMORIA)} entrada(s) previas.")
        except Exception as e:
            logger.warning(f"No se pudo cargar la caché de Ollama ({ruta}): {e}")


def _guardar_cache() -> None:
    ruta = config.OLLAMA_CACHE_ARCHIVO
    try:
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(_CACHE_MEMORIA, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.warning(f"No se pudo guardar la caché de Ollama ({ruta}): {e}")


def _validar_respuesta(data: dict) -> Optional[dict]:
    claves_requeridas = {"es_mismo_puesto", "confianza", "coincidencia_nombre_especifico",
                          "requiere_revision_humana", "explicacion"}
    if not claves_requeridas.issubset(data.keys()):
        return None
    if not isinstance(data["es_mismo_puesto"], bool):
        return None
    try:
        confianza = float(data["confianza"])
    except (TypeError, ValueError):
        return None
    if not (0.0 <= confianza <= 1.0):
        return None
    data["confianza"] = confianza
    return data


def consultar_ollama(
    puesto_a: str, puesto_b: str, tipo_catalogo: Optional[str], niveles_permitidos: list,
) -> Optional[dict]:
    """
    Pregunta a Ollama si `puesto_a` y `puesto_b` son el mismo puesto.
    Regresa el dict de respuesta validado, o None si Ollama no está
    disponible, la respuesta no es JSON válido, o hubo cualquier error
    (en cuyo caso el llamador debe tratar el caso como revisión manual,
    NUNCA asumir una coincidencia).
    """
    if not config.OLLAMA_ENABLED:
        return None

    payload_pregunta = {
        "excel_o_word": puesto_a,
        "otra_fuente": puesto_b,
        "tipo_catalogo": tipo_catalogo,
        "niveles_permitidos": niveles_permitidos,
    }

    _cargar_cache()
    clave = _clave_cache(payload_pregunta)
    if clave in _CACHE_MEMORIA:
        logger.info("Respuesta de Ollama tomada de caché (sin nueva consulta).")
        return _CACHE_MEMORIA[clave]

    try:
        import requests
    except ImportError:
        logger.warning("El paquete 'requests' no está instalado; Ollama no se puede consultar.")
        return None

    try:
        respuesta = requests.post(
            f"{config.OLLAMA_HOST}/api/chat",
            json={
                "model": config.OLLAMA_MODEL,
                "messages": [
                    {"role": "system", "content": _PROMPT_SISTEMA},
                    {"role": "user", "content": json.dumps(payload_pregunta, ensure_ascii=False)},
                ],
                "format": "json",
                "stream": False,
            },
            timeout=config.OLLAMA_TIMEOUT_SEGUNDOS,
        )
        respuesta.raise_for_status()
        contenido = respuesta.json()["message"]["content"]
        data = json.loads(contenido)
    except Exception as e:
        logger.warning(f"Ollama no disponible o falló la consulta ({e}); el caso queda en revisión manual.")
        return None

    data_validada = _validar_respuesta(data)
    if data_validada is None:
        logger.warning(f"Ollama respondió un JSON con forma inesperada: {data!r}; se descarta.")
        return None

    _CACHE_MEMORIA[clave] = data_validada
    _guardar_cache()
    return data_validada
