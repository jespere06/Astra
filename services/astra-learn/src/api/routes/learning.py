from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from src.db.database import get_db
from src.services.dashboard_service import DashboardService
from src.infrastructure.repositories.job_repo import JobRepository
from src.middleware.auth import get_current_tenant

router = APIRouter(prefix="/v1/learning", tags=["Learning Dashboard"])

@router.get("/status")
def get_status(
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    service = DashboardService(db)
    return service.get_learning_status(tenant_id)

@router.get("/jobs")
def list_jobs(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=100),
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    repo = JobRepository(db)
    items, total = repo.get_jobs_by_tenant(tenant_id, skip=(page-1)*limit, limit=limit)
    
    return {
        "data": items,
        "meta": {
            "page": page,
            "limit": limit,
            "total": total
        }
    }

@router.get("/metrics/{job_id}")
def get_job_metrics(
    job_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    service = DashboardService(db)
    data = service.get_job_analytics(tenant_id, job_id)
    
    if not data:
        raise HTTPException(status_code=404, detail="Métricas no encontradas para este Job o ID inválido")
        
    return data

# --- VALIDATION (PIPELINE) ---

from pydantic import BaseModel
from typing import Optional
from src.core.validator import SemanticValidator

class ValidateRequest(BaseModel):
    raw_text: str
    target_text: str
    current_start: float
    last_valid_end: Optional[float] = None

# Global instance for caching model
validator_instance = None

@router.post("/validate")
async def validate_pair(req: ValidateRequest):
    global validator_instance
    if not validator_instance:
         validator_instance = SemanticValidator()
    
    result = await validator_instance.validate_pair(
        req.raw_text,
        req.target_text,
        req.current_start,
        req.last_valid_end
    )
    return result

# --- BATCH INGEST ---

from typing import List, Dict, Any
from src.db.models.queue import TrainingQueue, QueueStatus

class IngestPair(BaseModel):
    raw_text: str
    target_text: str
    metadata: Dict[str, Any] = {}
    tenant_id: str

@router.post("/batch_ingest")
async def batch_ingest(pairs: List[IngestPair], db: Session = Depends(get_db)):
    """
    Ingests and validates a batch of training pairs.
    """
    global validator_instance
    if not validator_instance:
         validator_instance = SemanticValidator()
    
    results = []
    
    for p in pairs:
        # Validate
        start_time = p.metadata.get("start", 0.0)
        val_res = await validator_instance.validate_pair( 
             p.raw_text, 
             p.target_text, 
             current_start=start_time
        )
        
        # Map status
        status = QueueStatus.PENDING 
        if val_res["status"] == "GREEN":
            status = QueueStatus.READY
        elif val_res["status"] == "YELLOW":
            status = QueueStatus.PENDING_REVIEW
        elif val_res["status"] == "RED":
            status = QueueStatus.DISCARDED
            
        # Create Queue Item
        item = TrainingQueue(
            tenant_id=p.tenant_id,
            data_json={
                "instruction": "Transcribe the audio exactly.",
                "input": p.raw_text,
                "output": p.target_text,
                "metadata": {**p.metadata, **val_res} 
            },
            status=status,
            validation_score=val_res["score"], 
            validation_reasoning=val_res["reasoning"]
        )
        db.add(item)
        results.append({ "status": status, "score": val_res["score"], "reason": val_res["reasoning"] })
    
    db.commit()
    return {"processed": len(results), "details": results}
