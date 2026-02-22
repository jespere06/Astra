import logging
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from redis.asyncio import Redis
from src.models.training_job import TrainingJob
from src.schemas.job_dtos import JobStatus
from src.config import settings

logger = logging.getLogger(__name__)

TRAINING_JOB_PREFIX = "training_job:"
TENANT_TRAINING_INDEX = "training_jobs:tenant:"

class TrainingJobRepository:
    """
    Repositorio para persistir el estado de los trabajos de entrenamiento en Redis.
    """
    def __init__(self, redis: Redis):
        self.redis = redis
        self.ttl = 86400 * 7 # 1 semana

    async def create(self, job: TrainingJob) -> TrainingJob:
        key = f"{TRAINING_JOB_PREFIX}{job.id}"
        index_key = f"{TENANT_TRAINING_INDEX}{job.tenant_id}"
        
        data = job.model_dump()
        # Serialize complex types
        for k, v in data.items():
            if k in ("rows", "source_urls", "training_config", "result_summary", "execution_mode") and v is not None:
                if k == "execution_mode":
                    data[k] = v.value
                else:
                    data[k] = json.dumps(v)
            elif k == "status":
                data[k] = v.value
            elif v is None:
                data[k] = ""
        
        pipe = self.redis.pipeline()
        pipe.hset(key, mapping=data) # type: ignore
        pipe.expire(key, self.ttl)
        pipe.zadd(index_key, {job.id: time.time()})
        await pipe.execute()
        
        logger.info(f"📝 Training Job {job.id} creado para tenant {job.tenant_id}")
        return job

    async def update_status(self, job_id: str, status: JobStatus):
        key = f"{TRAINING_JOB_PREFIX}{job_id}"
        await self.redis.hset(key, "status", status.value)
        logger.info(f"🔄 Training Job {job_id} → {status.value}")

    async def complete_job(self, job_id: str, results: Dict[str, Any]):
        key = f"{TRAINING_JOB_PREFIX}{job_id}"
        updates = {
            "status": JobStatus.COMPLETED.value,
            "result_summary": json.dumps(results),
            "finished_at": datetime.now(timezone.utc).isoformat()
        }
        await self.redis.hset(key, mapping=updates) # type: ignore
        logger.info(f"✅ Training Job {job_id} completado")

    async def update_external_id(self, job_id: str, external_id: str):
        key = f"{TRAINING_JOB_PREFIX}{job_id}"
        await self.redis.hset(key, "external_job_id", external_id)

    async def fail_job(self, job_id: str, error: str):
        key = f"{TRAINING_JOB_PREFIX}{job_id}"
        updates = {
            "status": JobStatus.FAILED.value,
            "error": error,
            "finished_at": datetime.now(timezone.utc).isoformat()
        }
        await self.redis.hset(key, mapping=updates) # type: ignore
        logger.error(f"❌ Training Job {job_id} falló: {error}")

    async def get_job(self, job_id: str) -> Optional[TrainingJob]:
        key = f"{TRAINING_JOB_PREFIX}{job_id}"
        data = await self.redis.hgetall(key)
        if not data:
            return None
            
        # Deserialize
        processed = {}
        for k, v in data.items():
            k_str = k.decode() if isinstance(k, bytes) else k
            val = v.decode() if isinstance(v, bytes) else v
            
            if k_str in ("rows", "source_urls", "training_config", "result_summary"):
                processed[k_str] = json.loads(val) if val else ({} if k_str not in ("source_urls", "rows") else [])
            elif val == "":
                processed[k_str] = None
            else:
                processed[k_str] = val
                
        return TrainingJob(**processed)