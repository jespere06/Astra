from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from src.services.storage import AssetService
from src.infrastructure.redis_client import get_redis
from src.models.session_store import SessionStore

router = APIRouter(prefix="/v1/session", tags=["Assets"])

@router.post(
    "/{session_id}/upload-asset", 
    status_code=status.HTTP_201_CREATED,
    summary="Subir Anexo/Evidencia",
    description="Carga una imagen (JPEG/PNG) para ser indexada en el acta. Aplica deduplicación y optimización automática.",
    responses={
        201: {"description": "Activo procesado exitosamente"},
        413: {"description": "El archivo excede el límite de 10MB"}
    }
)
async def upload_session_asset(
    session_id: str,
    file: UploadFile = File(..., description="Archivo de imagen (binary)"),
    redis = Depends(get_redis)
):
    """
    Sube una imagen (evidencia/anexo) a la sesión actual.
    Implementa deduplicación proactiva contra la AssetLibrary.
    """
    store = SessionStore(redis)
    asset_service = AssetService(store)

    try:
        content = await file.read()
        # Límite de tamaño (ej. 10MB)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(413, "Archivo demasiado grande (Max 10MB)")

        result = await asset_service.process_asset_upload(
            session_id, file.filename, content
        )
        return result

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Avoid leaking internal errors details to client unless safe
        print(f"Internal error processing asset: {e}")
        raise HTTPException(status_code=500, detail="Error procesando activo")
