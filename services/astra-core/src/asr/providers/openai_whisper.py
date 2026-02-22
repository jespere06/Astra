import io
import logging
from openai import AsyncOpenAI, APIError, APITimeoutError
from ..base import ASRProvider

logger = logging.getLogger(__name__)

class OpenAIWhisperAPI(ASRProvider):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("OPENAI_API_KEY es requerida para este proveedor.")
        self.client = AsyncOpenAI(api_key=api_key)

    async def transcribe(self, audio_content: bytes, filename: str = "audio.wav", language: str = "es") -> str:
        # OpenAI requiere un objeto tipo archivo con atributo 'name'
        audio_file = io.BytesIO(audio_content)
        audio_file.name = filename

        try:
            transcript = await self.client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language,
                response_format="text"
            )
            return transcript
        except APITimeoutError:
            logger.error("Timeout conectando con OpenAI Whisper API")
            raise Exception("ASR Service Timeout")
        except APIError as e:
            logger.error(f"Error en OpenAI API: {str(e)}")
            raise Exception(f"ASR Provider Error: {e.message}")
        except Exception as e:
            logger.exception("Error inesperado en transcripción")
            raise e
