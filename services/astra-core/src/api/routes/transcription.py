import boto3
import io
import asyncio
from botocore.config import Config
from fastapi import APIRouter, UploadFile, File, Form, Depends, WebSocket, WebSocketDisconnect, HTTPException, status
from src.config import get_settings, Settings
from src.logic.scheduler import governor
from src.schemas.qos_models import TaskPriority, QoSResult
from src.api.schemas import UrlTranscriptionRequest

router = APIRouter(prefix="/v1/transcribe", tags=["Transcription"])

@router.post(
    "/batch", 
    response_model=QoSResult,
    status_code=status.HTTP_200_OK,
    summary="Procesamiento Batch (Archivo)"
)
async def batch_transcription(
    file: UploadFile = File(..., description="Archivo de audio (wav, mp3, m4a)"),
    tenant_id: str = Form(..., description="ID del inquilino"),
    provider: str = Form("deepgram", description="Proveedor ASR (deepgram, whisper, openai)"),
    priority: TaskPriority = Form(TaskPriority.INGEST_BATCH)
):
    """
    Endpoint principal para procesamiento de archivos completos.
    Utiliza semáforos para gestionar la carga.
    """
    if not file:
        raise HTTPException(status_code=400, detail="No file provided")
    
    content = await file.read()
    
    # Delegar al Gobernador
    result = await governor.process_request(content, priority, tenant_id, provider)
    
    if result.status == "failed":
        raise HTTPException(status_code=500, detail=result.qos_meta.error_details)
        
    return result

@router.post(
    "/url",
    response_model=QoSResult,
    summary="Procesamiento desde URL (S3/Internal)"
)
async def url_transcription(
    req: UrlTranscriptionRequest,
    settings: Settings = Depends(get_settings)
):
    """
    Descarga el audio de S3/MinIO y lo procesa.
    Optimizada para archivos grandes con Threading.
    """
    try:
        # 1. Configurar Cliente S3 con Timeouts Extendidos
        s3_config = Config(
            connect_timeout=120,   # 2 minutos para conectar
            read_timeout=1800,     # 30 minutos para leer/descargar el archivo completo
            retries={'max_attempts': 5}
        )

        s3 = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name="us-east-1",
            config=s3_config
        )

        # 2. Parsear URI (s3://bucket/key)
        if not req.audio_url.startswith("s3://"):
             raise HTTPException(400, "Solo se soportan URIs s3:// internas.")
             
        path_parts = req.audio_url.replace("s3://", "").split("/", 1)
        if len(path_parts) < 2:
             raise HTTPException(400, "Formato de URI S3 inválido.")
             
        bucket = path_parts[0]
        key = path_parts[1]

        # 3. Descargar a Memoria en un Hilo Separado (Non-Blocking)
        print(f"⬇️ Core descargando audio de S3: {bucket}/{key}")
        buffer = io.BytesIO()
        
        loop = asyncio.get_running_loop()
        # Esto evita que se congele el servidor mientras descarga archivos pesados
        await loop.run_in_executor(None, s3.download_fileobj, bucket, key, buffer)
        
        audio_bytes = buffer.getvalue()
        print(f"✅ Descarga completada: {len(audio_bytes) / 1024 / 1024:.2f} MB")

        # 4. Enviar al transcriptor (Deepgram por defecto desde Ingest)
        result = await governor.process_request(audio_bytes, req.priority, req.tenant_id, req.provider)
        
        if result.status == "failed":
             raise HTTPException(500, detail=result.qos_meta.error_details)
             
        return result

    except Exception as e:
        print(f"❌ Error crítico en proxy de transcripción: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.websocket("/stream")
async def websocket_endpoint(
    websocket: WebSocket
):
    """
    Endpoint Legacy para Streaming en tiempo real.
    """
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_bytes()
            if not data:
                break
            text = await governor.process_stream_chunk(data, provider="deepgram")
            if text.strip():
                await websocket.send_json({"text": text.strip(), "partial": False})
    except WebSocketDisconnect:
        print("Cliente desconectado del stream")
    except Exception as e:
        print(f"Error en websocket: {e}")
        await websocket.close(code=1011)