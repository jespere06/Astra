from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from src.db.database import SessionLocal
from src.db.models.queue import TrainingQueue, QueueStatus
import uuid
import enum

router = APIRouter(prefix="/v1/review", tags=["Review"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Enums
class ReviewStatus(str, enum.Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    READY = "READY"
    DISCARDED = "DISCARDED"

class ResolutionDecision(str, enum.Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EDIT = "EDIT"

# Request/Response Models
class ReviewItem(BaseModel):
    id: uuid.UUID
    tenant_id: str
    data_json: Dict[str, Any]
    validation_score: Optional[float]
    validation_reasoning: Optional[str]
    created_at: str

    class Config:
        from_attributes = True

    @classmethod
    def from_orm(cls, obj):
        # Helper to convert created_at datetime to string
        data = super().from_orm(obj)
        data.created_at = obj.created_at.isoformat() if obj.created_at else None
        return data

class ResolveRequest(BaseModel):
    queue_id: str
    decision: ResolutionDecision
    edited_text: Optional[str] = None
    new_start: Optional[float] = None
    new_end: Optional[float] = None

# Endpoints

@router.get("/pending/{tenant_id}", response_model=List[ReviewItem])
def get_pending_reviews(tenant_id: str, limit: int = 50, db: Session = Depends(get_db)):
    """
    Get items pending manual review (Yellow Zone).
    """
    import boto3
    s3_client = boto3.client('s3')

    items = db.query(TrainingQueue).filter(
        TrainingQueue.tenant_id == tenant_id,
        TrainingQueue.status == QueueStatus.PENDING_REVIEW
    ).order_by(TrainingQueue.created_at.desc()).limit(limit).all()
    
    results = []
    for item in items:
        data = ReviewItem.from_orm(item)
        # Inject presigned URL for audio
        if data.data_json and "metadata" in data.data_json:
            s3_key = data.data_json["metadata"].get("s3_key")
            if s3_key:
                try:
                    url = s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': 'astra-ingest-raw', 'Key': s3_key},
                        ExpiresIn=3600
                    )
                    data.data_json["metadata"]["audio_url"] = url
                except Exception as e:
                    print(f"Error generating presigned URL for {s3_key}: {e}")
        results.append(data)

    return results

@router.post("/resolve")
def resolve_review(req: ResolveRequest, db: Session = Depends(get_db)):
    """
    Human decision on a review item.
    """
    item = db.query(TrainingQueue).filter(TrainingQueue.id == req.queue_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if req.decision == ResolutionDecision.APPROVE:
        item.status = QueueStatus.READY
    
    elif req.decision == ResolutionDecision.REJECT:
        item.status = QueueStatus.DISCARDED
    
    elif req.decision == ResolutionDecision.EDIT:
        # Edit Case: Human adjusted text or timestamps
        # We need to update data_json.
        current_data = dict(item.data_json)
        
        # Update text if provided (Assuming 'output' is Target/Acta text we're editing?)
        # Or maybe 'input' (Evidence)?
        # For alignment: Usually we edit the transcription or the aligned text to match better.
        # Let's assume 'input' is Transcription, 'output' is Target.
        # If human edits text, let's assume they edit 'output' to match audio reality better?
        # Or 'input' to fix transcription error?
        # The prompt for UI implies: "Verdad Oficial (Acta)" vs "Evidencia Audio".
        # Usually Acta is immutable (Truth). Audio/Transcription is evidence.
        # But if validation fails, maybe we discard the pair.
        # If we edit, maybe we fix transcription errors?
        # Let's assume generic text edit capability for now.
        if req.edited_text: 
             current_data["input"] = req.edited_text # Edit the evidence
        
        # Update metadata timestamp if trimmed
        if req.new_start is not None or req.new_end is not None:
             meta = current_data.get("metadata", {})
             if req.new_start is not None: meta["start"] = req.new_start
             if req.new_end is not None: meta["end"] = req.new_end
             current_data["metadata"] = meta
        
        item.data_json = current_data
        item.status = QueueStatus.READY

    db.commit()
    return {"status": "resolved", "new_status": item.status, "id": str(item.id)}
