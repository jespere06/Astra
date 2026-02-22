from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import datetime

from src.db.base import get_db
from src.core.admin.label_manager import LabelManager
from src.db.models import EntityType

router = APIRouter(prefix="/v1/admin", tags=["Admin"])

class LabelRequest(BaseModel):
    tenant_id: str
    entity_hash: str
    label_name: str
    entity_type: str = "TEMPLATE" 

class UnlabeledTemplateResponse(BaseModel):
    id: str
    structure_hash: str
    variables: List[str]
    created_at: str

@router.post("/label")
def set_label(
    req: LabelRequest,
    db: Session = Depends(get_db)
):
    """Asigna una etiqueta humana a un hash estructural."""
    try:
        type_enum = EntityType(req.entity_type)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid entity type")

    manager = LabelManager(db)
    final_label = manager.assign_label(
        req.tenant_id, 
        req.entity_hash, 
        req.label_name, 
        type_enum
    )
    return {"status": "success", "label_assigned": final_label}

@router.get("/unlabeled/templates/{tenant_id}", response_model=List[UnlabeledTemplateResponse])
def get_unlabeled(
    tenant_id: str,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    """Lista templates pendientes de etiquetado."""
    manager = LabelManager(db)
    templates = manager.get_unlabeled_templates(tenant_id, limit)
    
    return [
        UnlabeledTemplateResponse(
            id=str(t.id),
            structure_hash=t.structure_hash,
            variables=t.variables_metadata or [],
            created_at=t.created_at.isoformat()
        ) for t in templates
    ]