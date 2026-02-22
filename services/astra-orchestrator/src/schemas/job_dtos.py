from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ExecutionMode(str, Enum):
    FULL_TRAINING = "FULL_TRAINING"
    DATA_PREP_ONLY = "DATA_PREP_ONLY"

class JobStatus(str, Enum):
    PENDING = "PENDING"
    MINING = "MINING"
    TRAINING = "TRAINING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TrainingJobRequest(BaseModel):
    tenant_id: str
    rows: List[Dict[str, Any]] = []
    source_urls: List[str] = []
    execution_mode: ExecutionMode = ExecutionMode.DATA_PREP_ONLY
    training_config: Optional[Dict[str, Any]] = {}

class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    result_summary: Optional[Dict[str, Any]] = None
    rows: Optional[List[Dict[str, Any]]] = None