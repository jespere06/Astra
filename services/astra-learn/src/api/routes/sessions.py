from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any
from src.db.database import get_db
from src.db.models.session import TrainingSession
from src.middleware.auth import get_current_tenant

# Importante: El prefijo coincide con lo que espera el frontend
router = APIRouter(prefix="/v1/learning", tags=["Sessions"])

class CreateSessionRequest(BaseModel):
    name: str

@router.get("/sessions")
def get_sessions(
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    sessions = db.query(TrainingSession).filter(
        TrainingSession.tenant_id == tenant_id
    ).order_by(TrainingSession.created_at.desc()).all()
    
    return [
        {
            "id": s.id,
            "name": s.name,
            "tenant_id": s.tenant_id,
            "rows": s.rows or [],
            "created": s.created_at.isoformat()
        }
        for s in sessions
    ]

@router.post("/sessions")
def create_session(
    req: CreateSessionRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    new_session = TrainingSession(
        tenant_id=tenant_id,
        name=req.name,
        rows=[]
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    
    return {
        "id": new_session.id,
        "name": new_session.name,
        "tenant_id": new_session.tenant_id,
        "rows": [],
        "created": new_session.created_at.isoformat()
    }

@router.put("/sessions/{session_id}/rows")
def update_session_rows(
    session_id: str,
    rows: List[Dict[str, Any]] = Body(..., embed=True),
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id,
        TrainingSession.tenant_id == tenant_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.rows = rows
    db.commit()
    
    return {"status": "success", "rows_count": len(rows)}

@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    tenant_id: str = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    session = db.query(TrainingSession).filter(
        TrainingSession.id == session_id,
        TrainingSession.tenant_id == tenant_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    db.delete(session)
    db.commit()
    return {"status": "deleted"}
