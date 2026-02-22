from pydantic import BaseModel
from typing import Optional
from src.schemas.qos_models import TaskPriority

class UrlTranscriptionRequest(BaseModel):
    audio_url: str
    tenant_id: str
    provider: str = "deepgram"
    priority: TaskPriority = TaskPriority.INGEST_BATCH
