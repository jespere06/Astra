from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from src.db.models import JobStatus

class IngestBatchRequest(BaseModel):
    tenant_id: str
    file_urls: List[str]  # En producción usaríamos HttpUrl, string por simplicidad local

class IngestJobResponse(BaseModel):
    job_id: UUID
    tenant_id: str
    status: JobStatus
    created_at: datetime
    error_log: Optional[str] = None

    class Config:
        from_attributes = True