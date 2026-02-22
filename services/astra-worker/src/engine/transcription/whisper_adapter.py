"""
Adaptador de Whisper (faster-whisper) para la interfaz unificada ITranscriber.

Soporta modelos: tiny, base, small, medium, large-v2, large-v3, large-v3-turbo.
Usa Lazy Loading para evitar consumir VRAM al importar el módulo.
"""

import io
import logging
import math
from typing import Dict, Optional, Any, List

from src.engine.transcription.interface import (
    ITranscriber,
    TranscriptResult,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

# Defaults razonables para procesamiento batch de audios largos (actas)
_DEFAULTS = {
    "model_size": "large-v3-turbo",
    "device": "cuda",
    "compute_type": "float16",      # float16 en GPU, int8 en CPU
    "beam_size": 5,
    "language": "es",
    "vad_filter": True,
    "vad_parameters": {
        "min_silence_duration_ms": 500,
    },
    "word_timestamps": False,
    "condition_on_previous_text": True,
}


def _logprob_to_confidence(avg_logprob: float) -> float:
    """
    Mapea avg_logprob (normalmente entre -1 y 0) a un rango [0, 1].
    Whisper reporta log-probs negativos; más cercano a 0 = más confianza.
    """
    # Clamp y mapeo lineal simple  (-1 → 0.0,  0 → 1.0)
    clamped = max(-1.0, min(0.0, avg_logprob))
    return round(1.0 + clamped, 4)


class WhisperTranscriber(ITranscriber):
    """
    Adaptador de `faster-whisper` (CTranslate2) para la interfaz unificada.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = {**_DEFAULTS, **(config or {})}
        self._model = None

    # ── Lazy Loading ──────────────────────────

    def _ensure_loaded(self):
        if self._model is not None:
            return

        from faster_whisper import WhisperModel

        model_size = self._config["model_size"]
        device = self._config["device"]
        compute_type = self._config["compute_type"]

        logger.info(
            f"🔄 Cargando Whisper ({model_size}) en {device} "
            f"[compute={compute_type}]..."
        )

        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )
        logger.info("✅ Whisper cargado y listo.")

    # ── ITranscriber ──────────────────────────

    def transcribe(
        self,
        audio_path: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        self._ensure_loaded()
        merged = {**self._config, **(config or {})}
        return self._run(audio_path, merged)

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        self._ensure_loaded()
        merged = {**self._config, **(config or {})}
        buf = io.BytesIO(audio_bytes)
        return self._run(buf, merged)

    def is_loaded(self) -> bool:
        return self._model is not None

    def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("🧹 Whisper descargado de memoria.")

    @property
    def provider_name(self) -> str:
        return f"whisper/{self._config['model_size']}"

    # ── Internal ──────────────────────────────

    def _run(self, source, cfg: Dict) -> TranscriptResult:
        segments_gen, info = self._model.transcribe(
            source,
            beam_size=cfg.get("beam_size", 5),
            language=cfg.get("language", "es"),
            vad_filter=cfg.get("vad_filter", True),
            vad_parameters=cfg.get("vad_parameters"),
            word_timestamps=cfg.get("word_timestamps", False),
            condition_on_previous_text=cfg.get("condition_on_previous_text", True),
        )

        segments: List[TranscriptSegment] = []
        texts: List[str] = []

        for seg in segments_gen:
            text = seg.text.strip()
            if not text:
                continue
            segments.append(
                TranscriptSegment(
                    start=round(seg.start, 3),
                    end=round(seg.end, 3),
                    text=text,
                    confidence=_logprob_to_confidence(seg.avg_logprob),
                )
            )
            texts.append(text)

        duration = segments[-1].end if segments else 0.0

        return TranscriptResult(
            text=" ".join(texts),
            segments=segments,
            language=info.language,
            language_probability=round(info.language_probability, 4),
            duration_seconds=round(duration, 3),
            provider=self.provider_name,
            metadata={
                "model_size": cfg["model_size"],
                "compute_type": cfg["compute_type"],
                "beam_size": cfg.get("beam_size"),
                "vad_filter": cfg.get("vad_filter"),
            },
        )
