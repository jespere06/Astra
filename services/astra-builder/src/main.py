from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
from src.core.composer import DocumentComposer

app = FastAPI(title="ASTRA Builder")

class ContentBlock(BaseModel):
    type: str
    target_placeholder: Optional[str] = None
    data: Any
    # audio_metadata para auditoría futura

class BuildRequest(BaseModel):
    session_id: str
    tenant_id: str
    skeleton_id: str
    skeleton_version_id: Optional[str] = None
    client_timezone: str = "UTC"
    blocks: List[ContentBlock]

@app.post("/v1/builder/generate")
async def generate_document(req: BuildRequest):
    try:
        composer = DocumentComposer(req.session_id, req.tenant_id, req.client_timezone)
        
        # 1. Descargar Skeleton (Versionado)
        composer.load_skeleton(req.skeleton_id, req.skeleton_version_id)
        
        # 2. Procesar Bloques
        composer.process_blocks([b.dict() for b in req.blocks])
        
        # 3. Finalizar y Subir
        s3_key = composer.finalize()
        
        return {
            "status": "success", 
            "docx_key": s3_key,
            "message": "Documento generado y almacenado exitosamente."
        }
        
    except Exception as e:
        # En producción, loguear stacktrace completo
        # import traceback
        # traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
