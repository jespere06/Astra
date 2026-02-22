"""
ASTRA-WORKER: Orquestador Serverless para RunPod.
"""
import json
import logging
import os
import time
import uuid
import runpod
from dataclasses import asdict

from src.config import settings
from src.storage import download_audio, upload_result
from src.webhook import notify_completion
from src.engine.transcription.factory import create_transcriber

# ── Logging ──
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger("ASTRA-WORKER")


def process_job(job):
    """
    Lógica core de transcripción adaptada para RunPod.
    Recibe el objeto 'job' de RunPod que contiene 'input'.
    """
    job_input = job.get("input", {})
    
    # 1. Extracción de Parámetros Dinámicos
    # El ID viene del orquestador o usamos el ID de RunPod
    astra_job_id = job_input.get("job_id") or job.get("id")
    tenant_id = job_input.get("tenant_id", "unknown_tenant")
    input_audio_url = job_input.get("input_audio_url")
    provider = job_input.get("transcription_provider", settings.TRANSCRIPTION_PROVIDER)
    
    # Configuración de salida (S3 keys)
    output_bucket = job_input.get("output_s3_bucket", settings.OUTPUT_S3_BUCKET)
    output_key = job_input.get("output_s3_key") or f"transcripts/{tenant_id}/{astra_job_id}.json"
    
    # Override de webhook si viene en el input
    webhook_url = job_input.get("webhook_url", settings.WEBHOOK_URL)
    # Nota: Actualizamos settings temporalmente para que el módulo webhook.py lo vea
    settings.WEBHOOK_URL = webhook_url

    t_start = time.time()
    timings = {}

    logger.info(f"═══ Procesando Job {astra_job_id} (Tenant: {tenant_id}) ═══")

    if not input_audio_url:
        return {"error": "INPUT_AUDIO_URL no proporcionada"}

    local_audio = None
    local_output = None

    try:
        # ── 2. Descarga ──
        t0 = time.time()
        audio_ext = _get_ext(input_audio_url)
        local_audio = os.path.join(settings.TEMP_DIR, f"input_{astra_job_id}{audio_ext}")
        download_audio(input_audio_url, local_audio)
        timings["download_s"] = round(time.time() - t0, 2)
        logger.info(f"  ⏱ Descarga completada: {timings['download_s']}s")

        # ── 3. Transcripción ──
        t0 = time.time()
        # Construimos config combinando defaults con inputs específicos si los hubiera
        engine_config = _build_engine_config() 
        engine = create_transcriber(provider, engine_config)

        logger.info(f"  🎙️ Transcribiendo con {engine.provider_name}...")
        result = engine.transcribe(local_audio)
        timings["transcription_s"] = round(time.time() - t0, 2)
        
        # ── 4. Serialización ──
        output_data = {
            "job_id": astra_job_id,
            "tenant_id": tenant_id,
            "text": result.text,
            "segments": [asdict(s) for s in result.segments],
            "language": result.language,
            "duration_seconds": result.duration_seconds,
            "provider": result.provider,
            "metadata": result.metadata,
            "runpod_job_id": job.get("id")
        }

        local_output = os.path.join(settings.TEMP_DIR, f"result_{astra_job_id}.json")
        with open(local_output, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        # ── 5. Subida a S3 ──
        t0 = time.time()
        output_uri = upload_result(local_output, output_bucket, output_key)
        timings["upload_s"] = round(time.time() - t0, 2)

        # ── 6. Notificación y Retorno ──
        timings["total_s"] = round(time.time() - t_start, 2)
        metrics = {
            **timings,
            "provider": result.provider,
            "audio_duration_s": result.duration_seconds,
        }

        # Notificamos al orquestador
        notify_completion(
            job_id=astra_job_id,
            status="COMPLETED",
            output_url=output_uri,
            metrics=metrics,
        )

        logger.info(f"✅ Job {astra_job_id} finalizado exitosamente.")
        
        # Retornamos el resultado para que RunPod lo marque como completado en su API también
        return {
            "status": "COMPLETED",
            "output_url": output_uri,
            "metrics": metrics
        }

    except Exception as e:
        logger.error(f"❌ Error en Job {astra_job_id}: {e}", exc_info=True)
        timings["total_s"] = round(time.time() - t_start, 2)
        
        notify_completion(
            job_id=astra_job_id,
            status="FAILED",
            error=str(e),
            metrics=timings,
        )
        # Retornamos error para que RunPod reintente si está configurado, o marque fallo
        return {"error": str(e)}

    finally:
        # Limpieza agresiva para mantener el contenedor ligero (Warm Start)
        _cleanup_files([local_audio, local_output])


def _build_engine_config() -> dict:
    """Construye config del motor desde env vars estáticas."""
    return {
        "model_size": settings.WHISPER_MODEL_SIZE,
        "device": settings.WHISPER_DEVICE,
        "compute_type": settings.WHISPER_COMPUTE_TYPE,
        "model_name": settings.PARAKEET_MODEL,
        "api_key": settings.OPENAI_API_KEY,
    }


def _get_ext(url: str) -> str:
    path = url.split("?")[0]
    for ext in (".wav", ".mp3", ".ogg", ".flac", ".m4a", ".webm"):
        if path.lower().endswith(ext):
            return ext
    return ".wav"


def _cleanup_files(paths):
    for p in paths:
        if p and os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

# ── Entrypoint RunPod ──
if __name__ == "__main__":
    logger.info("🚀 Iniciando ASTRA Worker en modo Serverless...")
    runpod.serverless.start({"handler": process_job})
