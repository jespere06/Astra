from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import json

from src.db.database import get_db
from src.logic.guard_manager import GuardManager
from src.api.schemas.snapshot_dto import SnapshotResponse, VerificationResponse
from src.api.dependencies import verify_snapshot_ownership
from src.db.models import Snapshot

router = APIRouter(prefix="/v1", tags=["Snapshots"])

@router.post(
    "/snapshots", 
    response_model=SnapshotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sellar Documento (WORM)"
)
async def create_snapshot(
    file: UploadFile = File(..., description="Archivo DOCX original"),
    tenant_id: str = Form(...),
    session_id: str = Form(...),
    metadata_json: Optional[str] = Form("{}", description="JSON string con metadatos extra"),
    db: Session = Depends(get_db)
):
    """
    Ingesta un documento, calcula su integridad canónica (ignorando metadatos volátiles),
    lo firma con la llave del tenant y lo almacena en modo inmutable.
    """
    # Validación de tipo
    if file.content_type not in [
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream" # A veces llega así
    ]:
        # Log error for better debugging
        # logger.warning(f"Invalid content type: {file.content_type}")
        pass

    try:
        meta_dict = json.loads(metadata_json) if metadata_json else {}
    except:
        meta_dict = {}

    manager = GuardManager(db)
    
    try:
        snapshot = await manager.seal_artifact(
            file, tenant_id, session_id, meta_dict
        )
        
        return SnapshotResponse(
            snapshot_id=str(snapshot.id),
            tenant_id=snapshot.tenant_id,
            root_hash=snapshot.root_hash,
            # Retornamos una "firma" visual para el cliente (puede ser el hash cifrado o la DEK pública)
            signature=f"sig_{snapshot.id}_{snapshot.root_hash[:8]}", 
            artifact_url=snapshot.artifact_url,
            s3_version_id=snapshot.s3_version_id,
            created_at=snapshot.created_at.isoformat()
        )
    except Exception as e:
        raise HTTPException(500, f"Error interno de sellado: {str(e)}")

@router.post(
    "/verify",
    response_model=VerificationResponse,
    summary="Verificar Integridad Canónica"
)
async def verify_snapshot(
    snapshot: Snapshot = Depends(verify_snapshot_ownership),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Recibe un archivo (que pudo haber sido abierto y guardado en Word) y verifica
    si su contenido semántico sigue siendo idéntico al original sellado.
    """
    manager = GuardManager(db)
    
    try:
        # Pasamos el id del snapshot validado por la dependencia
        result = await manager.verify_integrity(str(snapshot.id), file)
        
        return VerificationResponse(
            is_valid=result["is_valid"],
            snapshot_id=str(snapshot.id),
            verification_timestamp=result["timestamp"],
            audit_report={
                "stored_hash": result["stored_hash"],
                "calculated_hash": result["calculated_hash"],
                "match_status": "INTEGRO" if result["is_valid"] else "ALTERADO"
            }
        )
    except ValueError:
        raise HTTPException(404, "Snapshot no encontrado")
    except Exception as e:
        raise HTTPException(500, f"Error de verificación: {str(e)}")
