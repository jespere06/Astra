"""
JobManager — Orquestador principal del ciclo de vida de Jobs batch.

Coordina:
  1. Subida de audio a S3
  2. Creación del Job en Redis
  3. Despacho al worker en RunPod
  4. Manejo de retries
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from redis.asyncio import Redis

from src.config import settings
from src.infrastructure.storage_service import StorageService
from src.jobs.models import Job, JobStatus
from src.jobs.store import JobStore
from src.jobs.runpod_client import RunPodClient

logger = logging.getLogger(__name__)


class JobManager:
    def __init__(self, redis: Redis, storage: StorageService):
        self.store = JobStore(redis)
        self.storage = storage
        self.runpod = RunPodClient()

    async def submit_job(
        self,
        tenant_id: str,
        audio_content: bytes,
        filename: str = "audio.wav",
        provider: str = "whisper",
    ) -> Job:
        """
        Pipeline completo: Upload → Create → Dispatch.
        
        Args:
            tenant_id: ID del tenant
            audio_content: Audio en bytes
            filename: Nombre original del archivo
            provider: Motor de transcripción (whisper/parakeet)
        
        Returns:
            Job con status DISPATCHED
        """
        # 1. Crear Job en estado QUEUED
        job = Job(tenant_id=tenant_id, provider=provider)
        await self.store.create(job)

        try:
            # 2. Subir audio a S3 → UPLOADING
            await self.store.update_status(job.id, JobStatus.UPLOADING)

            s3_key = f"batch-input/{tenant_id}/{job.id}/{filename}"
            await self.storage.upload_generic_file(
                settings.S3_BATCH_BUCKET, s3_key, audio_content
            )

            # Generar URL presignada para el worker (24h)
            presigned_url = self.storage.s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.S3_BATCH_BUCKET, "Key": s3_key},
                ExpiresIn=86400,
            )

            await self.store.update_status(
                job.id, JobStatus.UPLOADING,
                input_s3_key=s3_key,
                input_url=presigned_url,
            )

            # 3. Despachar a RunPod → DISPATCHED
            result = await self._dispatch_to_runpod(job, presigned_url)

            now = datetime.now(timezone.utc).isoformat()
            await self.store.update_status(
                job.id, JobStatus.DISPATCHED,
                runpod_job_id=result.get("id", ""),
                started_at=now,
            )

            return await self.store.get(job.id)

        except Exception as e:
            logger.error(f"❌ Error en submit_job {job.id}: {e}")
            await self.store.update_status(
                job.id, JobStatus.FAILED,
                error=str(e)[:500],
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
            return await self.store.get(job.id)

    async def handle_webhook(
        self,
        job_id: str,
        status: str,
        output_url: str = "",
        metrics: dict = None,
        error: str = "",
    ) -> Optional[Job]:
        """
        Procesa el callback del worker (COMPLETED o FAILED).
        Si FAILED y quedan retries, re-despacha automáticamente.
        """
        now = datetime.now(timezone.utc).isoformat()

        if status == "COMPLETED":
            return await self.store.update_status(
                job_id, JobStatus.COMPLETED,
                output_url=output_url,
                metrics=metrics or {},
                finished_at=now,
            )

        elif status == "FAILED":
            # ¿Queda algún retry?
            retry_count = await self.store.increment_retry(job_id)

            if retry_count <= settings.JOB_MAX_RETRIES:
                logger.warning(
                    f"⚠️ Job {job_id} falló (intento {retry_count}/{settings.JOB_MAX_RETRIES}). "
                    f"Reintentando..."
                )
                await self.store.update_status(job_id, JobStatus.RETRYING, error=error)

                # Recuperar job y re-despachar
                job = await self.store.get(job_id)
                if job and job.input_url:
                    try:
                        result = await self._dispatch_to_runpod(job, job.input_url)
                        await self.store.update_status(
                            job_id, JobStatus.DISPATCHED,
                            runpod_job_id=result.get("id", ""),
                        )
                        return await self.store.get(job_id)
                    except Exception as e:
                        logger.error(f"❌ Retry dispatch failed: {e}")

            # Sin retries o retry dispatch falló
            return await self.store.update_status(
                job_id, JobStatus.FAILED,
                error=error,
                finished_at=now,
            )

        return await self.store.get(job_id)

    async def _dispatch_to_runpod(self, job: Job, audio_url: str) -> dict:
        """Construye el payload y despacha al worker."""
        # Webhook URL que el worker llamará
        webhook_url = f"{settings.WEBHOOK_CALLBACK_BASE_URL}/webhooks/worker"

        input_payload = {
            "job_id": job.id,
            "tenant_id": job.tenant_id,
            "input_audio_url": audio_url,
            "transcription_provider": job.provider,
            "output_s3_bucket": settings.S3_BATCH_BUCKET,
            "output_s3_key": f"batch-output/{job.tenant_id}/{job.id}/result.json",
            "webhook_url": webhook_url,
            "webhook_secret": settings.WEBHOOK_SECRET,
            # S3 credentials for the worker
            "s3_endpoint_url": settings.S3_ENDPOINT_URL,
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
        }

        return await self.runpod.dispatch_job(input_payload)
