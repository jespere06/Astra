import logging
import httpx
import pybreaker
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

# 1. Definición del Circuit Breaker (Abierto tras 5 fallos, cerrado tras 60s)
core_cb = pybreaker.CircuitBreaker(
    fail_max=5, 
    reset_timeout=60,
    name="ASTRA_CORE_CB"
)

class ResilienceManager:
    """
    Wrapper de resiliencia para llamadas salientes a servicios críticos.
    """
    
    @staticmethod
    @core_cb # El Circuit Breaker envuelve todo el proceso
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True
    )
    async def call_core(client: httpx.AsyncClient, url: str, files: dict, data: dict, timeout: float):
        """
        Llamada a CORE con reintentos y protección de circuito.
        """
        response = await client.post(
            url, 
            files=files, 
            data=data, 
            timeout=timeout
        )
        # Forzar excepción en 5xx para que el CB cuente el fallo
        if response.status_code >= 500:
            logger.error(f"CORE devolvió error crítico: {response.status_code}")
            raise httpx.HTTPStatusError(
                "Error interno del motor de IA", 
                request=response.request, 
                response=response
            )
        return response
