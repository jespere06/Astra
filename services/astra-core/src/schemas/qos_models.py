from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class TaskPriority(str, Enum):
    LIVE_SESSION = "live"    # Streaming (WebSockets)
    INGEST_BATCH = "batch"   # Procesamiento de archivos

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    AUDIO_PENDING = "audio_pending" # Para fallback

class FailoverContext(BaseModel):
    provider_used: str = "local_gpu"
    failover_occurred: bool = False
    error_details: Optional[str] = None
    s3_fallback_url: Optional[str] = None

class QoSResult(BaseModel):
    """Resultado unificado del procesamiento"""
    text: Optional[str] = None
    segments: Optional[list] = None
    language: Optional[str] = "es"
    duration: float = 0.0
    status: ProcessingStatus
    qos_meta: FailoverContext = Field(default_factory=FailoverContext)
