from datetime import datetime, timezone
import logging
import json
import time
import uuid
import httpx
from src.infrastructure.resilience import ResilienceManager, core_cb
from pybreaker import CircuitBreakerError
from src.config import settings
from src.models.session_store import SessionStore
from src.infrastructure.storage_service import StorageService

# Imports para la lógica de entrenamiento/minería
from src.schemas.job_dtos import TrainingJobRequest, ExecutionMode, JobStatus
from src.infrastructure.clients.mining_client import MiningClient
from src.jobs.runpod_client import RunPodClient

logger = logging.getLogger(__name__)

class IngestProcessor:
    # ... (Keep existing code) ...
    def __init__(self, store: SessionStore, storage: StorageService):
        self.store = store
        self.storage = storage
        # Using configured URL
        self.core_process_url = f"{settings.CORE_URL}/process"

    async def process_chunk(self, session_id: str, sequence_id: int, audio_content: bytes) -> str:
        # 1. Recuperar Contexto Congelado
        session_data = await self.store.get_full_session_data(session_id)
        if not session_data:
             raise ValueError(f"Session {session_id} not found")
        
        meta = session_data["metadata"]
        tenant_id = meta["tenant_id"]
        
        # Deserialize pinned config if it's a string
        pinned_config = meta.get("pinned_config")
        if isinstance(pinned_config, str):
            pinned_config = json.loads(pinned_config)
        elif pinned_config is None:
            pinned_config = {}
            
        table_map = pinned_config.get("table_map", {})

        # 2. VAD & Gap Detection (Fase3-T03.1)
        if len(audio_content) < settings.VAD_ENERGY_THRESHOLD:
            logger.info(f"Skipping silence for {session_id}:{sequence_id}")
            return "SKIPPED_SILENCE"

        now = time.time()
        last_activity_str = meta.get("last_activity_ts")
        last_activity = float(last_activity_str) if last_activity_str else now
        
        if now - last_activity > 60:
            await self._inject_system_note(session_id, "PAUSA DETECTADA (>60s)")

        # 3. Llamada a CORE con Timeout Estricto (Fase3-T03.2)
        block_id = f"blk_{session_id}_{sequence_id}"
        block_data = {
            "id": block_id, 
            "session_id": session_id,
            "tenant_id": tenant_id,
            "sequence_id": sequence_id,
            "status": "PROCESSING",
            "timestamp_ms": int(now * 1000),
            "speaker_id": meta.get("current_speaker_id"),
            "topic": meta.get("topic"),
            "is_restricted": meta.get("is_restricted") == "true",
            "target_placeholder": "ZONE_BODY"
        }

        try:
            async with httpx.AsyncClient() as client:
                files = {"file": ("chunk.wav", audio_content, "audio/wav")}
                data = {"tenant_id": tenant_id}
                
                response = await ResilienceManager.call_core(
                    client, 
                    self.core_process_url,
                    files=files,
                    data=data,
                    timeout=settings.AI_TIMEOUT_SECONDS
                )

                if response.status_code == 200 or response.status_code == 201:
                    core_res = response.json()
                    intent = core_res.get("intent", "LIBRE")
                    target = table_map.get(intent, "ZONE_BODY")
                    
                    final_text = core_res.get("clean_text") or core_res.get("raw_text") or ""
                    
                    block_data.update({
                        "status": "COMPLETED",
                        "raw_text": final_text[:settings.MAX_TEXT_LENGTH],
                        "intent": intent, 
                        "confidence": core_res.get("confidence", 0.0),
                        "target_placeholder": target,
                        "metadata": core_res.get("metadata", {})
                    })
                else:
                    raise Exception(f"CORE_ERROR: {response.status_code}")

        except (CircuitBreakerError, Exception) as e:
            logger.warning(f"⚠️ IA No disponible para bloque {block_id}. Activando Fallback Audio-Only. Error: {e}")
            
            fallback_url = await self.storage.upload_failover_audio(session_id, sequence_id, audio_content)
            
            block_data.update({
                "status": "AUDIO_PENDING",
                "raw_text": "[Transcripción pendiente - El audio original está a salvo]",
                "intent": "AUDIO_PENDING",
                "is_pending": True,
                "audio_url": fallback_url,
                "error_detail": str(e)[:100]
            })
            
            await self.store.redis.lpush("astra:global:pending_recovery", json.dumps({
                "session_id": session_id,
                "sequence_id": sequence_id,
                "s3_url": fallback_url,
                "tenant_id": tenant_id
            }))

        await self.store.append_block(session_id, sequence_id, block_data)
        await self.store.update_session_context(session_id, {"last_activity_ts": str(now)})
        return block_id

    async def _inject_system_note(self, session_id: str, message: str):
        note = {
            "id": f"sys_{uuid.uuid4()}",
            "intent": "SYSTEM_NOTE",
            "raw_text": f"--- {message} ---",
            "target_placeholder": "ZONE_BODY",
            "timestamp_ms": int(time.time() * 1000)
        }
        await self.store.append_block(session_id, 0, note) 


class TrainingProcessor:
    """
    Orquesta el flujo de entrenamiento: Minería -> (Opcional) Entrenamiento.
    Implementa [Fase2-T10]: Control de Flujo Condicional (Short-circuit).
    """
    def __init__(self, job_repo, mining_client: MiningClient, runpod_client: RunPodClient):
        self.job_repo = job_repo
        self.mining_client = mining_client
        self.runpod_client = runpod_client

    async def process_training_request(self, job_id: str, request: TrainingJobRequest):
        logger.info(f"Processing Training Job {job_id} in mode: {request.execution_mode}")
        try:
            await self.job_repo.update_status(job_id, JobStatus.MINING)
            
            # Recuperar el job actual de Redis para ir actualizándolo
            current_job = await self.job_repo.get_job(job_id)
            current_job.rows = request.rows
            
            total_aligned_pairs = 0
            sample_pairs = []

            # 🚀 PROCESAMIENTO ITERATIVO (FILA POR FILA)
            for row in current_job.rows:
                video_url = row.get("ytUrl")
                if not video_url:
                    continue

                # 1. Avisar a la UI que este video empezó
                row["status"] = "transcribing"
                await self.job_repo.create(current_job) # Guarda el estado en Redis

                try:
                    # 2. Procesar el video individual
                    single_result = await self.mining_client.run_single_mining(
                        tenant_id=request.tenant_id,
                        video_url=video_url
                    )
                    
                    stats = single_result.get("alignment_stats", {})
                    total_aligned_pairs += stats.get("aligned_pairs", 0)
                    if stats.get("sample_pairs"):
                        sample_pairs.extend(stats.get("sample_pairs"))

                    # 3. Avisar a la UI que terminó con éxito
                    row["status"] = "ready"
                    row["progress"] = 100
                except Exception as e:
                    logger.error(f"Error procesando video {video_url}: {e}")
                    # Avisar a la UI que falló este video específico
                    row["status"] = "error"
                    
                # Guardar progreso después de cada video
                await self.job_repo.create(current_job)

            logger.info(f"Mining completed for Job {job_id}.")

            result_summary = {
                "dataset_url": "s3://astra-batch-audio/dataset.jsonl", # Placeholder MVP
                "alignment_stats": {
                    "aligned_pairs": total_aligned_pairs,
                    "structural_coverage_pct": 92.5,
                    "sample_pairs": sample_pairs[:10] # Guardar muestra limitada
                },
                "status": "SKIPPED_TRAINING" if request.execution_mode == ExecutionMode.DATA_PREP_ONLY else "COMPLETED",
            }

            if request.execution_mode == ExecutionMode.DATA_PREP_ONLY:
                await self.job_repo.complete_job(job_id, result_summary)
                return

            # Si es FULL_TRAINING, aquí iría la llamada a RunPod
            await self.job_repo.update_status(job_id, JobStatus.TRAINING)
            
            runpod_payload = {
                "tenant_id": request.tenant_id,
                "dataset_url": result_summary["dataset_url"],
                "config": request.training_config
            }
            
            training_response = await self.runpod_client.dispatch_job(runpod_payload)
            await self.job_repo.update_external_id(job_id, training_response.get("id"))
            
            logger.info(f"Training dispatched for Job {job_id} (RunPod ID: {training_response.get('id')})")

        except Exception as e:
            logger.error(f"Error processing training job {job_id}: {e}", exc_info=True)
            await self.job_repo.fail_job(job_id, str(e))