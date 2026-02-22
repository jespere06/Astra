"""
ASTRA Transcription Engine — Unified Interface.

Provee una abstracción agnóstica para múltiples motores de transcripción ASR,
permitiendo hot-swap entre Whisper, Parakeet, APIs externas, etc.

Uso típico:

    from src.engine.transcription import create_transcriber

    engine = create_transcriber("whisper")      # o "parakeet", "openai_api"
    result = engine.transcribe("/path/to/audio.wav")
"""

from src.engine.transcription.interface import ITranscriber, TranscriptResult, TranscriptSegment
from src.engine.transcription.factory import create_transcriber

__all__ = [
    "ITranscriber",
    "TranscriptResult",
    "TranscriptSegment",
    "create_transcriber",
]
