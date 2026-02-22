import os
import logging
import time
import requests
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class CoreTranscriptionClient:
    """
    Cliente para consumir los servicios de transcripción de ASTRA-CORE.
    Soporta la estrategia de enviar URLs de S3 para procesamiento Cloud (Deepgram).
    """

    def __init__(self, base_url: str = None, api_key: str = None):
        # CORRECCIÓN: Apuntar al puerto 8002 (donde corre Core en npm run dev)
        # Si la env var no está, usar localhost:8002 en lugar de astra-core:8000
        default_url = "http://localhost:8002" 
        
        # Intentar leer de env vars comunes
        self.base_url = base_url or os.getenv("ASTRA_CORE_URL") or os.getenv("CORE_URL") or default_url
        
        # Asegurarse de no tener path extra si ya viene en la variable
        self.base_url = self.base_url.rstrip("/")
        
        self.api_key = api_key or os.getenv("ASTRA_INTERNAL_API_KEY", "")
        self.headers = {
            "X-Client-Id": "astra-ingest-miner",
            "Authorization": f"Bearer {self.api_key}"
        }

    def transcribe_url(self, audio_url: str, tenant_id: str, provider: str = "deepgram") -> Dict[str, Any]:
        """
        Solicita la transcripción de un archivo de audio alojado en una URL accesible (S3 presigned).
        """
        # CAMBIO: Apuntar al nuevo endpoint que acepta JSON
        endpoint = f"{self.base_url}/v1/transcribe/url"
        
        payload = {
            "audio_url": audio_url,
            "tenant_id": tenant_id,
            "provider": provider,
            "priority": "batch"
        }

        logger.info(f"🌐 Solicitando transcripción a Core ({provider}): {endpoint}")
        
        try:
            # Timeout generoso (1800 segundos = 30 minutos)
            response = requests.post(endpoint, json=payload, headers=self.headers, timeout=1800)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # Mock fallback para desarrollo si el endpoint no existe aún
                logger.warning("Endpoint de Core no encontrado. Retornando Mock.")
                return self._mock_response()
            else:
                response.raise_for_status()
                
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Error conectando con ASTRA-CORE: {e}")
            raise RuntimeError(f"Fallo en transcripción remota: {e}")

    def _mock_response(self):
        """Retorna una estructura válida para pruebas sin el servicio levantado."""
        return {
            "text": "Esta es una transcripción simulada para pruebas de integración.",
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "Esta es una", "speaker": "Speaker 1"},
                {"start": 2.0, "end": 5.0, "text": "transcripción simulada para pruebas.", "speaker": "Speaker 1"}
            ],
            "language": "es",
            "duration": 5.0
        }
