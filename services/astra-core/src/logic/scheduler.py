import asyncio
import logging
import concurrent.futures
from typing import Union, BinaryIO

from src.config import get_settings
from src.engine.transcription.factory import create_transcriber
from src.schemas.qos_models import TaskPriority, QoSResult, ProcessingStatus, FailoverContext

logger = logging.getLogger(__name__)

class ResourceGovernor:
    """
    Orquesta el acceso al motor de transcripción (ITranscriber).
    Implementa semáforos para limitar concurrencia en GPU y maneja
    la ejecución en ThreadPool para no bloquear el Event Loop de FastAPI.
    """

    def __init__(self):
        self.settings = get_settings()
        
        # Semáforo para controlar acceso concurrente (batch processing)
        self._gpu_semaphore = asyncio.Semaphore(self.settings.MAX_CONCURRENT_BATCH_JOBS)
        
        # ThreadPool para ejecución CPU-bound/red
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.settings.MAX_CONCURRENT_BATCH_JOBS + 2)
        
        # Caché de instancias de motores de transcripción
        self._engines = {}

    def get_engine(self, provider: str):
        if provider not in self._engines:
            config = {
                "model_size": self.settings.WHISPER_MODEL_SIZE,
                "device": self.settings.WHISPER_DEVICE,
                "compute_type": self.settings.WHISPER_COMPUTE_TYPE,
                "api_key": self.settings.DEEPGRAM_API_KEY
            }
            self._engines[provider] = create_transcriber(provider, config)
        return self._engines[provider]

    async def process_request(self, audio: bytes, priority: TaskPriority, tenant_id: str, provider: str = "deepgram") -> QoSResult:
        """
        Punto de entrada unificado para Batch y Requests HTTP únicos.
        """
        try:
            # Seleccionar motor dinámicamente
            engine = self.get_engine(provider)

            async with self._gpu_semaphore:
                logger.info(f"[{priority}] Iniciando transcripción para {tenant_id} con {engine.provider_name}...")
                
                # Ejecutar en hilo separado para no bloquear FastAPI
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    self._executor, 
                    engine.transcribe_bytes, 
                    audio
                )
                
                return QoSResult(
                    text=result.text,
                    segments=[vars(s) for s in result.segments],
                    language=result.language,
                    duration=result.duration_seconds,
                    status=ProcessingStatus.COMPLETED
                )

        except Exception as e:
            logger.error(f"Fallo en transcripción ({priority}): {e}")
            import traceback
            traceback.print_exc()
            return QoSResult(
                status=ProcessingStatus.FAILED,
                qos_meta=FailoverContext(error_details=str(e), failover_occurred=True)
            )

    async def process_stream_chunk(self, audio_chunk: bytes, provider: str = "deepgram") -> str:
        """
        Manejo optimizado para Streaming (Websockets).
        """
        loop = asyncio.get_running_loop()
        fast_config = {"beam_size": 1, "vad_filter": False}
        engine = self.get_engine(provider)
        
        try:
            result = await loop.run_in_executor(
                self._executor, 
                lambda: engine.transcribe_bytes(audio_chunk, fast_config)
            )
            return result.text
        except Exception as e:
            logger.error(f"Error en stream chunk: {e}")
            return ""

# Instancia global
governor = ResourceGovernor()