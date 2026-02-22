"""
Adaptador de APIs externas (OpenAI Whisper API, Azure Speech, etc.)
para la interfaz unificada ITranscriber.

Permite usar ASTRA sin GPU local, delegando la transcripción a un servicio cloud.
Útil como fallback o para desarrollo local sin CUDA.
"""

import io
import logging
import os
from typing import Dict, Optional, Any, List

from src.engine.transcription.interface import (
    ITranscriber,
    TranscriptResult,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "api_key": "",
    "model": "whisper-1",
    "language": "es",
    "response_format": "verbose_json",  # Para obtener segmentos con timestamps
}


class OpenAIAPITranscriber(ITranscriber):
    """
    Adaptador que delega la transcripción a la API de OpenAI (Whisper-1).
    No necesita GPU. Ideal para desarrollo o como fallback de producción.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = {**_DEFAULTS, **(config or {})}
        self._client = None

        # Resolver API key: config > ENV
        if not self._config["api_key"]:
            self._config["api_key"] = os.getenv("OPENAI_API_KEY", "")

    # ── Lazy Loading ──────────────────────────

    def _ensure_loaded(self):
        if self._client is not None:
            return

        from openai import OpenAI

        api_key = self._config["api_key"]
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY no configurada para el adaptador de API.")

        self._client = OpenAI(api_key=api_key)
        logger.info("✅ Cliente OpenAI API inicializado.")

    # ── ITranscriber ──────────────────────────

    def transcribe(
        self,
        audio_path: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        self._ensure_loaded()
        merged = {**self._config, **(config or {})}

        with open(audio_path, "rb") as f:
            return self._run(f, merged)

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        self._ensure_loaded()
        merged = {**self._config, **(config or {})}

        buf = io.BytesIO(audio_bytes)
        buf.name = "audio.wav"  # OpenAI requiere un nombre con extensión
        return self._run(buf, merged)

    def is_loaded(self) -> bool:
        return self._client is not None

    def unload(self) -> None:
        self._client = None
        logger.info("🧹 Cliente OpenAI API liberado.")

    @property
    def provider_name(self) -> str:
        return "openai_api/whisper-1"

    # ── Internal ──────────────────────────────

    def _run(self, file_obj, cfg: Dict) -> TranscriptResult:
        response = self._client.audio.transcriptions.create(
            model=cfg.get("model", "whisper-1"),
            file=file_obj,
            language=cfg.get("language", "es"),
            response_format=cfg.get("response_format", "verbose_json"),
        )

        # Parsear respuesta verbose_json
        if hasattr(response, "segments") and response.segments:
            segments = [
                TranscriptSegment(
                    start=round(seg.get("start", seg["start"]) if isinstance(seg, dict) else seg.start, 3),
                    end=round(seg.get("end", seg["end"]) if isinstance(seg, dict) else seg.end, 3),
                    text=(seg.get("text", "") if isinstance(seg, dict) else seg.text).strip(),
                    confidence=self._extract_confidence(seg),
                )
                for seg in response.segments
            ]
            full_text = " ".join(s.text for s in segments)
        else:
            # Fallback: respuesta plana
            full_text = response.text if hasattr(response, "text") else str(response)
            segments = [
                TranscriptSegment(start=0, end=0, text=full_text, confidence=0.85)
            ] if full_text.strip() else []

        duration = segments[-1].end if segments else 0.0

        return TranscriptResult(
            text=full_text.strip(),
            segments=segments,
            language=cfg.get("language", "es"),
            language_probability=getattr(response, "language_probability", 0.95) if hasattr(response, "language_probability") else 0.95,
            duration_seconds=round(duration, 3),
            provider=self.provider_name,
            metadata={"model": cfg.get("model"), "api": "openai"},
        )

    def _extract_confidence(self, seg) -> float:
        """Extrae confianza de un segmento de la API."""
        if isinstance(seg, dict):
            logprob = seg.get("avg_logprob", -0.3)
        else:
            logprob = getattr(seg, "avg_logprob", -0.3)
        # Normalizar a [0, 1]
        clamped = max(-1.0, min(0.0, logprob))
        return round(1.0 + clamped, 4)
