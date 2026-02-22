from fastapi import FastAPI, UploadFile, File, Form, HTTPException, status, Depends
from fastapi.responses import JSONResponse
import json
import logging
import time

from src.config import get_settings, Settings
from src.api.routes import router as core_router
from src.services.pipeline import SemanticPipeline
from src.schemas.process import ProcessingRequest
from src.logic.scheduler import governor
from src.schemas.qos_models import TaskPriority, ProcessingStatus

# Importar el listener
from src.infra.cache import RedisEventListener
from contextlib import asynccontextmanager
import asyncio

# Configuración de Logging Estructurado
logging.basicConfig(
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(module)s", "message": "%(message)s"}',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Variable global para el listener
event_listener = RedisEventListener()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Iniciar Listener de Fondo
    task = asyncio.create_task(event_listener.start())
    logger.info("🚀 Background Event Listener iniciado")
    
    yield
    
    # Shutdown
    await event_listener.stop()
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except asyncio.TimeoutError:
        pass
    logger.info("🛑 Background Event Listener detenido")

app = FastAPI(title="ASTRA-CORE", version="0.1.0", lifespan=lifespan)
app.include_router(core_router)

# Instancia Singleton del Pipeline
pipeline = SemanticPipeline()

# --- Routes ---

@app.get("/health")
async def health_check():
    """Health check endpoint para k8s/docker."""
    return {"status": "ok", "service": "astra-core", "version": "0.1.0"}

@app.post("/process_audio_qos")
async def process_audio_qos(
    file: UploadFile = File(...),
    priority: TaskPriority = Form(TaskPriority.LIVE_SESSION),
    tenant_id: str = Form(...),
    provider: str = Form("deepgram")
):
    """
    Endpoint con esteroides: Soporta failover y priorización de tráfico.
    """
    content = await file.read()
    result = await governor.process_request(content, priority, tenant_id, provider)
    
    if result.status == ProcessingStatus.AUDIO_PENDING:
        # Retornamos 202 Accepted indicando que el proceso no terminó pero el dato está seguro
        return JSONResponse(
            status_code=202, 
            content=result.model_dump()
        )
        
    return result

@app.post("/v1/process")
async def process_content(
    file: UploadFile = File(None),
    text: str = Form(None),
    tenant_id: str = Form(...),
    client_timezone: str = Form("UTC"),
    entities_dict: str = Form("{}"), # JSON string
    provider: str = Form("deepgram")
):
    """
    Endpoint principal de procesamiento semántico.
    Acepta Audio (File) o Texto (Form).
    """
    request_id = f"req_{int(time.time()*1000)}"
    logger.info(f"Processing request {request_id} for tenant {tenant_id}")

    try:
        try:
            entities = json.loads(entities_dict)
        except json.JSONDecodeError:
            entities = {}

        audio_bytes = await file.read() if file else None
        
        req = ProcessingRequest(
            tenant_id=tenant_id,
            client_timezone=client_timezone,
            entities_dictionary=entities,
            audio_content=audio_bytes,
            audio_filename=file.filename if file else None,
            text_content=text,
            flags={"provider": provider}
        )

        result = await pipeline.execute(req)
        result.metadata["request_id"] = request_id
        
        return result

    except ValueError as e:
        logger.warning(f"Validation error in {request_id}: {e}")
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        logger.error(f"Critical error in {request_id}: {e}", exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={
                "error": "Internal Processing Failure",
                "detail": str(e),
                "request_id": request_id
            }
        )