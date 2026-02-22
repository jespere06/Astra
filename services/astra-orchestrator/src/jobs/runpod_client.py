import httpx
import logging
import asyncio
from typing import Dict, Any, Optional
from src.config import settings

logger = logging.getLogger(__name__)

class RunPodError(Exception):
    """Excepción base para errores relacionados con RunPod."""
    pass

class RunPodClient:
    """
    Cliente de infraestructura para interactuar con RunPod Serverless API v2.
    """

    def __init__(self, api_key: str = None, endpoint_id: str = None):
        self.api_key = api_key or settings.RUNPOD_API_KEY
        self.endpoint_id = endpoint_id or settings.RUNPOD_ENDPOINT_ID
        
        if not self.api_key:
            logger.warning("RUNPOD_API_KEY no configurada. El cliente fallará en llamadas reales.")
        
        # URL Base: https://api.runpod.ai/v2/{endpoint_id}
        self.base_url = f"https://api.runpod.ai/v2/{self.endpoint_id}"
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        self.timeout = httpx.Timeout(
            settings.HTTP_TIMEOUT_READ, 
            connect=settings.HTTP_TIMEOUT_CONNECT
        )

    async def _request(self, method: str, path: str, json_data: Dict = None) -> Dict[str, Any]:
        """
        Wrapper interno para peticiones HTTP con manejo de errores y reintentos simples.
        """
        url = f"{self.base_url}{path}"
        retries = 3
        last_exception = None

        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.debug(f"RunPod Request: {method} {url} (Attempt {attempt+1})")
                    
                    response = await client.request(
                        method=method, 
                        url=url, 
                        headers=self.headers, 
                        json=json_data
                    )
                    
                    # Manejo específico de errores HTTP
                    response.raise_for_status()
                    return response.json()

            except httpx.HTTPStatusError as e:
                # No reintentar en errores de cliente 4xx (excepto quizás 429)
                if 400 <= e.response.status_code < 500:
                    logger.error(f"RunPod Client Error {e.response.status_code}: {e.response.text}")
                    raise RunPodError(f"Error de cliente RunPod: {e.response.text}") from e
                
                logger.warning(f"RunPod Server Error {e.response.status_code}. Retrying...")
                last_exception = e

            except httpx.RequestError as e:
                logger.warning(f"RunPod Network Error: {e}. Retrying...")
                last_exception = e
            
            # Backoff exponencial simple
            await asyncio.sleep(2 ** attempt)

        logger.error(f"RunPod Request Failed after {retries} attempts.")
        raise RunPodError(f"Fallo de comunicación con RunPod: {last_exception}") from last_exception

    async def submit_job(self, input_payload: Dict[str, Any]) -> str:
        """
        Despacha un trabajo de entrenamiento asíncrono.
        
        Args:
            input_payload: Diccionario con los parámetros del job (dataset_url, hiperparámetros).
                           Se envolverá automáticamente en la llave "input".
        
        Returns:
            str: El ID del trabajo asignado por RunPod.
        """
        # RunPod espera: { "input": { ... } }
        payload = {"input": input_payload}
        
        data = await self._request("POST", "/run", payload)
        
        job_id = data.get("id")
        if not job_id:
            raise RunPodError("La respuesta de RunPod no contiene 'id'.")
            
        logger.info(f"Job despachado a RunPod exitosamente. ID: {job_id}")
        return job_id

    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        Consulta el estado de un trabajo.
        
        Returns:
            Dict con keys normalizadas: id, status, output (si completed), error (si failed).
        """
        data = await self._request("GET", f"/status/{job_id}")
        return data

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancela un trabajo en ejecución o en cola.
        
        Returns:
            bool: True si la cancelación fue aceptada.
        """
        try:
            await self._request("POST", f"/cancel/{job_id}")
            logger.info(f"Job {job_id} cancelado.")
            return True
        except RunPodError:
            # Si falla la cancelación (ej. ya terminó o no existe), logueamos pero no crasheamos flujos críticos
            logger.warning(f"No se pudo cancelar el Job {job_id}")
            return False