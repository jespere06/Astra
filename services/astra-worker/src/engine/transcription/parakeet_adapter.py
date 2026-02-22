"""
Adaptador de NVIDIA Parakeet-TDT para la interfaz unificada ITranscriber.

Usa NVIDIA NeMo ASR (parakeet-tdt-0.6b-v3), optimizado para:
  - Throughput extremo (~2000x RTF en A100)
  - Bajo consumo de VRAM (~2GB)
  - Batching masivo de chunks

Requiere: nemo_toolkit[asr] instalado.
Lazy Loading: El modelo (600M params) solo se descarga/carga al primer transcribe().
"""

import io
import logging
import tempfile
import os
from typing import Dict, Optional, Any, List

from src.engine.transcription.interface import (
    ITranscriber,
    TranscriptResult,
    TranscriptSegment,
)

logger = logging.getLogger(__name__)

_DEFAULTS = {
    "model_name": "nvidia/parakeet-tdt-0.6b-v2",
    "device": "cuda",
    "batch_size": 64,        # Agresivo: la L4 tiene 22GB libres con este modelo
    "language": "es",        # Parakeet es multilingüe
}


class ParakeetTranscriber(ITranscriber):
    """
    Adaptador de NVIDIA Parakeet-TDT (NeMo) — optimizado para batch processing.

    Este modelo domina el Open ASR Leaderboard para inglés y tiene
    resultados muy competitivos en español. Su arquitectura FastConformer-TDT
    permite paralelismo real de GPU con un footprint mínimo de memoria.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = {**_DEFAULTS, **(config or {})}
        self._model = None

    # ── Lazy Loading ──────────────────────────

    def _ensure_loaded(self):
        if self._model is not None:
            return

        try:
            import nemo.collections.asr as nemo_asr
        except ImportError:
            raise RuntimeError(
                "NeMo ASR no está instalado. "
                "Instala con: pip install 'nemo_toolkit[asr]'"
            )

        model_name = self._config["model_name"]
        logger.info(f"🔄 Cargando Parakeet ({model_name})...")

        self._model = nemo_asr.models.ASRModel.from_pretrained(
            model_name=model_name,
        )

        # Mover a GPU si corresponde
        if self._config["device"] == "cuda":
            import torch
            if torch.cuda.is_available():
                self._model = self._model.cuda()
            else:
                logger.warning("CUDA no disponible. Parakeet funcionará en CPU (lento).")

        self._model.eval()
        logger.info(f"✅ Parakeet ({model_name}) cargado y listo.")

    # ── ITranscriber ──────────────────────────

    def transcribe(
        self,
        audio_path: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        self._ensure_loaded()
        merged = {**self._config, **(config or {})}
        return self._run_file(audio_path, merged)

    def transcribe_bytes(
        self,
        audio_bytes: bytes,
        config: Optional[Dict[str, Any]] = None,
    ) -> TranscriptResult:
        """
        NeMo requiere un archivo en disco, así que persistimos el buffer
        temporalmente. Para batch processing esto es irrelevante en latencia.
        """
        self._ensure_loaded()
        merged = {**self._config, **(config or {})}

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            return self._run_file(tmp_path, merged)
        finally:
            os.unlink(tmp_path)

    def is_loaded(self) -> bool:
        return self._model is not None

    def unload(self) -> None:
        if self._model is not None:
            del self._model
            self._model = None
            logger.info("🧹 Parakeet descargado de memoria.")

    @property
    def provider_name(self) -> str:
        return f"parakeet/{self._config['model_name'].split('/')[-1]}"

    # ── Internal ──────────────────────────────

    def _run_file(self, audio_path: str, cfg: Dict) -> TranscriptResult:
        """
        Ejecuta la transcripción de NeMo.
        NeMo retorna texto plano y opcionalmente timestamps por token.
        """
        batch_size = cfg.get("batch_size", 64)

        # NeMo transcribe acepta una lista de paths
        outputs = self._model.transcribe(
            [audio_path],
            batch_size=batch_size,
        )

        # NeMo puede retornar lista de strings o lista de Hypotheses
        # Dependiendo de la versión y configuración
        if isinstance(outputs, list):
            if len(outputs) > 0 and isinstance(outputs[0], str):
                full_text = outputs[0]
                segments = self._create_simple_segments(full_text)
            else:
                # Hypothesis object (NeMo ≥ 2.0)
                hyp = outputs[0]
                full_text = hyp.text if hasattr(hyp, 'text') else str(hyp)
                segments = self._extract_segments_from_hypothesis(hyp)
        else:
            full_text = str(outputs)
            segments = self._create_simple_segments(full_text)

        return TranscriptResult(
            text=full_text.strip(),
            segments=segments,
            language=cfg.get("language", "es"),
            language_probability=0.95,  # NeMo no reporta un score para el idioma
            duration_seconds=self._estimate_duration(audio_path),
            provider=self.provider_name,
            metadata={
                "model_name": cfg["model_name"],
                "batch_size": batch_size,
            },
        )

    def _create_simple_segments(self, text: str) -> List[TranscriptSegment]:
        """
        Fallback: si NeMo no da timestamps, creamos un segmento único.
        """
        if not text.strip():
            return []
        return [
            TranscriptSegment(
                start=0.0,
                end=0.0,   # Se actualiza post-procesamiento si es necesario
                text=text.strip(),
                confidence=0.90,  # Confianza estimada alta para Parakeet
            )
        ]

    def _extract_segments_from_hypothesis(self, hyp) -> List[TranscriptSegment]:
        """
        Extrae segmentos con timestamps de un objeto Hypothesis de NeMo.
        """
        segments: List[TranscriptSegment] = []

        # NeMo Hypothesis puede tener timestamp_words o timestamp_segments
        if hasattr(hyp, 'timestep') and hyp.timestep:
            # TDT timestamps: lista de (start, end, token)
            for ts in hyp.timestep:
                if hasattr(ts, 'start') and hasattr(ts, 'end'):
                    segments.append(
                        TranscriptSegment(
                            start=round(ts.start, 3),
                            end=round(ts.end, 3),
                            text=ts.word if hasattr(ts, 'word') else str(ts),
                            confidence=0.92,
                        )
                    )

        # Fallback si no hay timestamps
        if not segments:
            text = hyp.text if hasattr(hyp, 'text') else str(hyp)
            return self._create_simple_segments(text)

        return segments

    def _estimate_duration(self, audio_path: str) -> float:
        """Estima la duración del audio. Usa soundfile si está disponible."""
        try:
            import soundfile as sf
            info = sf.info(audio_path)
            return round(info.duration, 3)
        except Exception:
            return 0.0
