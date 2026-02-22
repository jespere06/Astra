"""
Webhook receiver para callbacks del ASTRA-WORKER.

POST /webhooks/worker  → Recibe notificación de job completado/fallido.
                         Verifica firma HMAC-SHA256.
"""
import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from redis.asyncio import Redis

from src.config import settings
from src.infrastructure.redis_client import get_redis
from src.infrastructure.storage_service import StorageService
from src.jobs.manager import JobManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

_storage = StorageService()


class WorkerWebhookPayload(BaseModel):
    job_id: str
    status: str           # "COMPLETED" | "FAILED"
    output_url: str = ""
    metrics: Dict[str, Any] = {}
    error: str = ""


def _verify_signature(body: bytes, signature_header: Optional[str]) -> bool:
    """Verifica la firma HMAC-SHA256 del payload."""
    if not settings.WEBHOOK_SECRET:
        # Sin secret configurado, aceptar todo (dev mode)
        return True

    if not signature_header:
        return False

    # Formato: "sha256=<hex>"
    if not signature_header.startswith("sha256="):
        return False

    expected = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    received = signature_header.replace("sha256=", "")
    return hmac.compare_digest(expected, received)


@router.post("/worker", status_code=200)
async def worker_webhook(request: Request):
    """
    Recibe la notificación del ASTRA-WORKER al completar o fallar un job.
    
    Headers requeridos:
      - X-Astra-Signature: sha256=<hmac_hex>  (si WEBHOOK_SECRET está configurado)
    
    Body:
      {
        "job_id": "abc-123",
        "status": "COMPLETED",
        "output_url": "s3://bucket/key.json",
        "metrics": { "total_s": 42.5, "provider": "whisper/large-v3-turbo" },
        "error": ""
      }
    """
    # 1. Leer body raw para verificar firma
    body = await request.body()
    signature = request.headers.get("X-Astra-Signature")

    if not _verify_signature(body, signature):
        logger.warning("🚫 Webhook rechazado: firma inválida")
        raise HTTPException(401, "Firma inválida")

    # 2. Parsear payload
    try:
        payload = WorkerWebhookPayload.model_validate_json(body)
    except Exception as e:
        raise HTTPException(400, f"Payload inválido: {e}")

    logger.info(
        f"📡 Webhook recibido: job={payload.job_id} status={payload.status}"
    )

    # 3. Procesar con JobManager
    redis = get_redis()
    try:
        manager = JobManager(redis, _storage)
        job = await manager.handle_webhook(
            job_id=payload.job_id,
            status=payload.status,
            output_url=payload.output_url,
            metrics=payload.metrics,
            error=payload.error,
        )

        if job:
            return {"received": True, "job_id": job.id, "final_status": job.status.value}
        else:
            return {"received": True, "job_id": payload.job_id, "warning": "Job not found"}

    finally:
        await redis.aclose()
