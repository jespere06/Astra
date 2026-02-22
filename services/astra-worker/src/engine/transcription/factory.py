"""
Factory para instanciar el motor de transcripción correcto.

Centraliza la creación para que el resto del sistema no necesite
conocer las clases concretas de cada adaptador.
"""

import logging
from typing import Dict, Optional, Any

from src.engine.transcription.interface import ITranscriber

logger = logging.getLogger(__name__)

# ── Registry de adaptadores ──────────────────

_ADAPTER_MAP = {
    # GPU Local: faster-whisper (CTranslate2)
    "whisper": "src.engine.transcription.whisper_adapter.WhisperTranscriber",
    "faster-whisper": "src.engine.transcription.whisper_adapter.WhisperTranscriber",

    # GPU Local: NVIDIA NeMo Parakeet
    "parakeet": "src.engine.transcription.parakeet_adapter.ParakeetTranscriber",
    "nemo": "src.engine.transcription.parakeet_adapter.ParakeetTranscriber",

    # API Remota: OpenAI
    "openai": "src.engine.transcription.openai_adapter.OpenAIAPITranscriber",
    "openai_api": "src.engine.transcription.openai_adapter.OpenAIAPITranscriber",
}


def _import_class(dotted_path: str):
    """Import dinámico de una clase desde su path punteado."""
    module_path, class_name = dotted_path.rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def create_transcriber(
    provider: str = "whisper",
    config: Optional[Dict[str, Any]] = None,
) -> ITranscriber:
    """
    Crea una instancia del transcriptor especificado.

    Args:
        provider:  Clave del motor a usar. Opciones:
                   'whisper'  | 'faster-whisper'  → WhisperTranscriber
                   'parakeet' | 'nemo'            → ParakeetTranscriber
                   'openai'   | 'openai_api'      → OpenAIAPITranscriber
        config:    Diccionario opcional de configuración específica del adaptador.

    Returns:
        Instancia de ITranscriber lista para usar (modelo cargado lazy).

    Raises:
        ValueError: Si el provider no está registrado.
    """
    provider_key = provider.lower().strip()

    if provider_key not in _ADAPTER_MAP:
        available = ", ".join(sorted(_ADAPTER_MAP.keys()))
        raise ValueError(
            f"Provider '{provider}' no reconocido. "
            f"Opciones disponibles: {available}"
        )

    dotted = _ADAPTER_MAP[provider_key]
    cls = _import_class(dotted)

    logger.info(f"🏭 Creando transcriber: {provider_key} → {cls.__name__}")
    return cls(config=config)


def register_adapter(name: str, dotted_path: str) -> None:
    """
    Registra un nuevo adaptador personalizado en runtime.
    Útil para plugins o extensiones de terceros.

    Ejemplo:
        register_adapter("deepgram", "my_package.deepgram_adapter.DeepgramTranscriber")
    """
    _ADAPTER_MAP[name.lower().strip()] = dotted_path
    logger.info(f"📦 Adaptador '{name}' registrado exitosamente.")
