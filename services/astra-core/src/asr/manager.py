import logging
from typing import Optional
from openai import APITimeoutError, RateLimitError, APIConnectionError

from src.asr.base import ASRProvider
# from src.asr.providers.openai_whisper import OpenAIWhisperAPI
from src.schemas.qos_models import FailoverContext, QoSResult, ProcessingStatus

logger = logging.getLogger(__name__)

class LocalWhisperProvider(ASRProvider):
    """Mock/Implementación temporal del proveedor local hasta que se integre la Fase 4"""
    async def transcribe(self, audio_content: bytes, filename: str = "audio.wav", language: str = "es") -> str:
        logger.info("🎙️ Usando Whisper LOCAL (Fallback)")
        # Simulación de transcripción local
        return "Texto transcrito localmente (Modo Failover)"

class ProviderManager:
    def __init__(self, saas_provider: ASRProvider, local_provider: ASRProvider):
        self.saas = saas_provider
        self.local = local_provider

    async def transcribe_with_failover(self, audio: bytes, filename: str) -> QoSResult:
        context = FailoverContext()
        
        # 1. Intento SaaS
        try:
            text = await self.saas.transcribe(audio, filename)
            context.provider_used = "saas"
            return QoSResult(text=text, status=ProcessingStatus.COMPLETED, qos_meta=context)
            
        except (APITimeoutError, RateLimitError, APIConnectionError, Exception) as e:
            logger.warning(f"⚠️ SaaS Falló ({type(e).__name__}). Iniciando Failover Local. Detalle: {e}")
            context.failover_occurred = True
            context.error_details = str(e)

        # 2. Intento Local (Hot-Swap)
        try:
            text = await self.local.transcribe(audio, filename)
            context.provider_used = "local"
            return QoSResult(text=text, status=ProcessingStatus.COMPLETED, qos_meta=context)
            
        except Exception as e:
            logger.error(f"❌ Fallo Total (SaaS + Local): {e}")
            context.provider_used = "none"
            context.error_details = f"Critical Failure: {str(e)}"
            # El scheduler se encargará de subir a S3, aquí retornamos estado de error controlado
            return QoSResult(status=ProcessingStatus.AUDIO_PENDING, qos_meta=context)
