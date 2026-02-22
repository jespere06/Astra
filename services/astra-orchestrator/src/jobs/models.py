"""
Modelos de datos para Jobs de transcripción batch.

Estado de máquina:
  QUEUED → UPLOADING → DISPATCHED → PROCESSING → COMPLETED
                                                → FAILED → RETRYING → DISPATCHED
"""
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
import uuid


class JobStatus(str, Enum):
    QUEUED      = "QUEUED"
    UPLOADING   = "UPLOADING"
    DISPATCHED  = "DISPATCHED"
    PROCESSING  = "PROCESSING"
    COMPLETED   = "COMPLETED"
    FAILED      = "FAILED"
    RETRYING    = "RETRYING"


class Job(BaseModel):
    """Representación de un Job de transcripción batch."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    tenant_id: str
    status: JobStatus = JobStatus.QUEUED
    provider: str = "whisper"

    # Input/Output
    input_url: str = ""           # URL del audio original (S3)
    input_s3_key: str = ""        # Key en S3 del audio subido
    output_url: str = ""          # URL del JSON resultado (S3)

    # RunPod tracking
    runpod_job_id: str = ""
    retry_count: int = 0

    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: Optional[str] = None
    finished_at: Optional[str] = None

    # Result
    error: str = ""
    metrics: Dict[str, Any] = Field(default_factory=dict)

    def to_redis_dict(self) -> Dict[str, str]:
        """Serializa para Redis Hash (todos los valores son strings)."""
        import json
        d = {}
        for k, v in self.model_dump().items():
            if isinstance(v, dict):
                d[k] = json.dumps(v)
            elif v is None:
                d[k] = ""
            else:
                d[k] = str(v)
        return d

    @classmethod
    def from_redis_dict(cls, data: Dict[str, str]) -> Job:
        """Deserializa desde Redis Hash."""
        import json
        if "metrics" in data and data["metrics"]:
            try:
                data["metrics"] = json.loads(data["metrics"])
            except (json.JSONDecodeError, TypeError):
                data["metrics"] = {}
        # Limpiar empty strings que son None
        for k in ("started_at", "finished_at"):
            if k in data and data[k] == "":
                data[k] = None
        return cls(**data)


# ── Schemas para API ──

class CreateJobRequest(BaseModel):
    provider: str = "whisper"
    language: str = "es"
    priority: str = "normal"    # normal | high


class CreateJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    id: str
    tenant_id: str
    status: str
    provider: str
    input_url: str
    output_url: str
    created_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    error: str
    metrics: Dict[str, Any]
    retry_count: int


class JobListResponse(BaseModel):
    jobs: list[JobStatusResponse]
    total: int
