from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.db.database import get_db
from src.logic.recovery import RecoveryEngine

router = APIRouter(prefix="/v1/guard", tags=["Recovery"])

@router.get("/time-travel/{session_id}")
async def time_travel_recovery(
    session_id: str,
    tenant_id: str = Query(..., description="ID del inquilino propietario"),
    at: datetime = Query(default_factory=datetime.utcnow, description="Timestamp objetivo (ISO8601)"),
    include_audio: bool = Query(False, description="Incluir audio original (requiere permisos elevados)"),
    db: Session = Depends(get_db)
):
    """
    Recupera el estado exacto de un acta en un punto del tiempo.
    Retorna un ZIP con el documento, evidencia y cadena de custodia.
    """
    engine = RecoveryEngine(db)
    
    # 1. Buscar Snapshot
    snapshot = engine.get_snapshot_at_time(session_id, at, tenant_id)
    
    if not snapshot:
        raise HTTPException(
            status_code=404, 
            detail=f"No se encontraron registros para la sesión {session_id} antes de {at}"
        )

    # 2. Generar Stream
    try:
        # Validar permisos para audio aquí si fuera necesario
        # if include_audio and not user_has_permission(): ...
        
        zip_stream = engine.generate_evidence_package(snapshot, include_audio)
        
        filename = f"evidencia_{session_id}_v{snapshot.version_number}.zip"
        
        return StreamingResponse(
            zip_stream,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except RuntimeError as e:
        # Error de integridad física
        raise HTTPException(status_code=412, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando paquete: {str(e)}")
