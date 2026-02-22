from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
import logging

from src.db.database import get_db
from src.db.models import Snapshot, AuditLog
from src.audio_archiver import AudioIntegrityService
from src.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/internal", tags=["Internal"])

class AudioHandoverRequest(BaseModel):
    session_id: str
    tenant_id: str
    s3_key: str
    s3_version_id: str = None

def verify_service_key(x_service_key: str = Header(...)):
    """Autenticación simple entre microservicios"""
    # En prod esto debería ser mTLS o IAM, para MVP usamos una shared key
    if x_service_key != settings.SYSTEM_SECRET_KEY: 
        raise HTTPException(status_code=403, detail="Invalid Service Key")

@router.post("/audio-handover")
async def confirm_audio_handover(
    req: AudioHandoverRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: str = Depends(verify_service_key)
):
    """
    Recibe notificación de que el audio ya está en el bucket WORM.
    Dispara la verificación de integridad en background.
    """
    # 1. Verificar que existe el snapshot (El documento ya debió ser sellado)
    snapshot = db.query(Snapshot).filter(
        Snapshot.session_id == req.session_id,
        Snapshot.tenant_id == req.tenant_id
    ).order_by(Snapshot.created_at.desc()).first()
    
    if not snapshot:
        raise HTTPException(404, "Snapshot de documento no encontrado para esta sesión")

    # 2. Disparar tarea de hashing (puede tardar minutos para audios largos)
    background_tasks.add_task(
        process_audio_integrity, 
        str(snapshot.id), 
        req.s3_key, 
        req.s3_version_id
    )
    
    return {"status": "processing", "message": "Verificación de audio iniciada"}

def process_audio_integrity(snapshot_id: str, s3_key: str, version_id: str):
    """Worker function para procesar el audio"""
    from src.db.database import SessionLocal
    local_db = SessionLocal()
    
    service = AudioIntegrityService()
    
    try:
        # 1. Calcular Hash
        audio_hash = service.calculate_audio_hash(s3_key, version_id)
        
        # 2. Actualizar Snapshot
        snap = local_db.query(Snapshot).get(snapshot_id)
        if snap:
            snap.audio_url = f"s3://{service.vault_bucket}/{s3_key}"
            snap.audio_hash = audio_hash
            snap.audio_s3_version = version_id
            
            # 3. Log de Auditoría
            audit = AuditLog(
                tenant_id=snap.tenant_id,
                snapshot_id=snap.id,
                actor_id="SYSTEM_AUDIO_ARCHIVER",
                action="AUDIO_SEAL",
                status="SUCCESS",
                metadata={"audio_hash": audio_hash}
            )
            local_db.add(audit)
            local_db.commit()
            logger.info(f"Integridad de audio procesada para snapshot {snapshot_id}")
            
    except Exception as e:
        local_db.rollback()
        logger.error(f"Error procesando audio para snapshot {snapshot_id}: {e}")
    finally:
        local_db.close()
