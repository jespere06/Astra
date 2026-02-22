from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from typing import List
from src.db.base import get_db
from src.db.models import Template, ZoneMapping, MappingOrigin
from src.api.schemas.mapping_dto import UnmappedTemplateDTO, BatchMappingRequest

router = APIRouter(prefix="/v1/config", tags=["Configuration"])

@router.get("/{tenant_id}/unmapped-templates", response_model=List[UnmappedTemplateDTO])
def get_unmapped_templates(tenant_id: str, db: Session = Depends(get_db)):
    """
    [Fase1-T07.1b] Obtiene templates que no tienen mapeo o cuyo mapeo no está bloqueado (auto).
    """
    # Left Join para encontrar templates sin mapeo
    stmt = db.query(Template).outerjoin(
        ZoneMapping, Template.id == ZoneMapping.template_id
    ).filter(
        Template.tenant_id == tenant_id,
        # Queremos los que no tienen mapeo O los que tienen mapeo automático (no revisado)
        (ZoneMapping.id == None) | (ZoneMapping.is_locked == False)
    ).limit(50) # Paginación implícita para UI

    results = stmt.all()
    
    dtos = []
    for tmpl in results:
        dtos.append(UnmappedTemplateDTO(
            template_id=tmpl.id,
            structure_hash=tmpl.structure_hash,
            preview_text=tmpl.preview_text or "(Sin previsualización disponible)",
            variables=tmpl.variables_metadata or []
        ))
    
    return dtos

@router.put("/{tenant_id}/mappings")
def update_mappings(
    tenant_id: str,
    payload: BatchMappingRequest,
    db: Session = Depends(get_db)
):
    """
    [Fase1-T07.1b] Guarda o actualiza mapeos manualmente. Bloquea el registro.
    """
    updated_count = 0
    
    for req in payload.mappings:
        # Verificar que el template pertenece al tenant
        tmpl = db.query(Template).filter_by(id=req.template_id, tenant_id=tenant_id).first()
        if not tmpl:
            continue 
            
        # Buscar mapeo existente
        mapping = db.query(ZoneMapping).filter_by(template_id=req.template_id).first()
        
        if mapping:
            mapping.zone_id = req.zone_id
            mapping.origin = MappingOrigin.HUMAN
            mapping.is_locked = True
            mapping.confidence_score = 1.0
        else:
            new_mapping = ZoneMapping(
                tenant_id=tenant_id,
                template_id=req.template_id,
                zone_id=req.zone_id,
                origin=MappingOrigin.HUMAN,
                is_locked=True,
                confidence_score=1.0,
                position_stats={} # Stats vacíos si es manual puro
            )
            db.add(new_mapping)
        
        updated_count += 1
    
    db.commit()
    return {"status": "success", "updated": updated_count}