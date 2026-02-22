from fastapi import Depends, Form, HTTPException, Request
from sqlalchemy.orm import Session
from src.db.database import get_db
from src.db.models import Snapshot

def verify_snapshot_ownership(
    request: Request,
    snapshot_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Dependencia para validar que el snapshot_id enviado en el formulario
    pertenece al tenant autenticado en el token.
    """
    tenant_id = getattr(request.state, "tenant_id", None)
    
    if not tenant_id:
         raise HTTPException(401, "No authenticated tenant context found.")

    snapshot = db.query(Snapshot).filter(
        Snapshot.id == snapshot_id
    ).first()
    
    if not snapshot:
        raise HTTPException(404, "Snapshot no encontrado")
        
    if snapshot.tenant_id != tenant_id:
        raise HTTPException(403, "ACCESO DENEGADO: Este recurso pertenece a otro inquilino.")
        
    return snapshot
