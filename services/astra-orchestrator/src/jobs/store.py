"""
JobStore — Persistencia Redis para Jobs de transcripción.

Key patterns:
  job:{id}                    → Hash con todos los campos del Job
  jobs:tenant:{tenant_id}     → Sorted Set (score=timestamp) para listado paginado
"""
import logging
import time
from typing import List, Optional

from redis.asyncio import Redis

from src.config import settings
from src.jobs.models import Job, JobStatus

logger = logging.getLogger(__name__)

JOB_PREFIX = "job:"
TENANT_INDEX_PREFIX = "jobs:tenant:"


class JobStore:
    def __init__(self, redis: Redis):
        self.redis = redis
        self.ttl = settings.JOB_TTL_SECONDS

    # ── CRUD ──────────────────────────────────

    async def create(self, job: Job) -> Job:
        """Persiste un nuevo Job en Redis."""
        key = f"{JOB_PREFIX}{job.id}"
        index_key = f"{TENANT_INDEX_PREFIX}{job.tenant_id}"

        pipe = self.redis.pipeline()
        pipe.hset(key, mapping=job.to_redis_dict())
        pipe.expire(key, self.ttl)
        # Index por tenant (score = timestamp para orden cronológico)
        pipe.zadd(index_key, {job.id: time.time()})
        pipe.expire(index_key, self.ttl)
        await pipe.execute()

        logger.info(f"📝 Job {job.id} creado para tenant {job.tenant_id}")
        return job

    async def get(self, job_id: str) -> Optional[Job]:
        """Recupera un Job por ID."""
        key = f"{JOB_PREFIX}{job_id}"
        data = await self.redis.hgetall(key)
        if not data:
            return None
        return Job.from_redis_dict(data)

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        **extra_fields,
    ) -> Optional[Job]:
        """
        Actualiza el status de un Job y opcionalmente otros campos.
        
        Uso:
            await store.update_status("abc", JobStatus.COMPLETED, output_url="s3://...")
        """
        key = f"{JOB_PREFIX}{job_id}"
        exists = await self.redis.exists(key)
        if not exists:
            logger.warning(f"Job {job_id} no encontrado para update")
            return None

        updates = {"status": status.value}
        for k, v in extra_fields.items():
            if isinstance(v, dict):
                import json
                updates[k] = json.dumps(v)
            elif v is None:
                updates[k] = ""
            else:
                updates[k] = str(v)

        await self.redis.hset(key, mapping=updates)
        logger.info(f"🔄 Job {job_id} → {status.value}")

        return await self.get(job_id)

    async def list_by_tenant(
        self,
        tenant_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[List[Job], int]:
        """Lista Jobs de un tenant, ordenados por creación (más reciente primero)."""
        index_key = f"{TENANT_INDEX_PREFIX}{tenant_id}"

        # Total
        total = await self.redis.zcard(index_key)

        # IDs paginados (reverso: más reciente primero)
        job_ids = await self.redis.zrevrange(index_key, offset, offset + limit - 1)

        jobs = []
        for jid in job_ids:
            job = await self.get(jid)
            if job:
                jobs.append(job)

        return jobs, total

    async def increment_retry(self, job_id: str) -> int:
        """Incrementa retry_count y retorna el nuevo valor."""
        key = f"{JOB_PREFIX}{job_id}"
        new_count = await self.redis.hincrby(key, "retry_count", 1)
        return new_count
