"""
Notificador Webhook — avisa al Orchestrator que el job terminó.
"""
import hashlib
import hmac
import json
import logging
import time
from typing import Dict, Any, Optional

import requests

from src.config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE = 2  # segundos


def notify_completion(
    job_id: str,
    status: str,
    output_url: str = "",
    metrics: Optional[Dict[str, Any]] = None,
    error: str = "",
):
    """
    POST al webhook del Orchestrator con el resultado del job.

    Payload:
        {
            "job_id": "abc-123",
            "status": "COMPLETED" | "FAILED",
            "output_url": "s3://bucket/key.json",
            "metrics": { "duration_s": 42.5, "provider": "whisper/large-v3-turbo" },
            "error": ""
        }
    """
    url = settings.WEBHOOK_URL
    if not url:
        logger.warning("⚠️ WEBHOOK_URL no configurada. Saltando notificación.")
        return

    payload = {
        "job_id": job_id,
        "status": status,
        "output_url": output_url,
        "metrics": metrics or {},
        "error": error,
    }

    headers = {"Content-Type": "application/json"}

    # HMAC signing para seguridad
    body_bytes = json.dumps(payload, sort_keys=True).encode()
    if settings.WEBHOOK_SECRET:
        signature = hmac.new(
            settings.WEBHOOK_SECRET.encode(),
            body_bytes,
            hashlib.sha256,
        ).hexdigest()
        headers["X-Astra-Signature"] = f"sha256={signature}"

    # Retry con backoff exponencial
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(f"📡 Notificando webhook (intento {attempt}/{MAX_RETRIES})...")
            resp = requests.post(url, data=body_bytes, headers=headers, timeout=10)
            resp.raise_for_status()
            logger.info(f"   ✅ Webhook respondió: {resp.status_code}")
            return
        except requests.RequestException as e:
            logger.warning(f"   ⚠️ Webhook falló: {e}")
            if attempt < MAX_RETRIES:
                wait = BACKOFF_BASE ** attempt
                logger.info(f"   ⏳ Reintentando en {wait}s...")
                time.sleep(wait)

    logger.error(f"❌ Webhook falló tras {MAX_RETRIES} intentos. Job {job_id} no notificado.")
