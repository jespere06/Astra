from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import uuid
from src.schemas.job_dtos import JobStatus, ExecutionMode

class TrainingJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    session_id: Optional[str] = None
    status: JobStatus = JobStatus.PENDING
    execution_mode: ExecutionMode = ExecutionMode.DATA_PREP_ONLY
    
    rows: List[Dict[str, Any]] = Field(default_factory=list)
    source_urls: List[str] = Field(default_factory=list)

    training_config: Dict[str, Any] = Field(default_factory=dict)
    
    # RunPod tracking
    external_job_id: Optional[str] = None
    
    # Results
    result_summary: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # Timestamps
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    finished_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()