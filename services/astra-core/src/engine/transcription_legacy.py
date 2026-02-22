import io
import logging
from faster_whisper import WhisperModel
from src.config import settings

logger = logging.getLogger(__name__)

class WhisperAdapter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WhisperAdapter, cls).__new__(cls)
            cls._instance._load_model()
        return cls._instance

    def _load_model(self):
        logger.info(f"🔄 Cargando Whisper ({settings.WHISPER_MODEL_SIZE}) en {settings.WHISPER_DEVICE}...")
        try:
            self.model = WhisperModel(
                settings.WHISPER_MODEL_SIZE, 
                device=settings.WHISPER_DEVICE, 
                compute_type=settings.WHISPER_COMPUTE_TYPE
            )
            logger.info("✅ Whisper cargado correctamente.")
        except Exception as e:
            logger.critical(f"❌ Error cargando Whisper: {e}")
            raise

    def transcribe(self, audio_bytes: bytes) -> dict:
        """
        Transcribe un stream de audio binario.
        """
        # faster-whisper acepta un file-like object
        audio_stream = io.BytesIO(audio_bytes)
        
        segments, info = self.model.transcribe(
            audio_stream, 
            beam_size=5,
            language="es",
            vad_filter=True # Filtrar silencios
        )

        # Consumir generador de segmentos
        text_segments = []
        full_text = []
        
        for segment in segments:
            text_segments.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text.strip(),
                "confidence": segment.avg_logprob
            })
            full_text.append(segment.text.strip())

        return {
            "text": " ".join(full_text),
            "segments": text_segments,
            "language": info.language,
            "language_probability": info.language_probability
        }
