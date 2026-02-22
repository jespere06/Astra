import asyncio
import json
import logging
import httpx
from datetime import datetime
from src.infrastructure.resilience import ResilienceManager
from src.models.session_store import SessionStore
from src.config import settings

logger = logging.getLogger(__name__)

async def download_from_s3(url: str) -> bytes:
    """Helper to download audio from presigned URL"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        resp.raise_for_status()
        return resp.content

async def recovery_worker(redis_client):
    store = SessionStore(redis_client)
    logger.info("👷 Worker de recuperación ASTRA activo...")
    
    # We need a configured core URL
    core_url = f"{settings.CORE_URL}/process"

    while True:
        try:
            # 1. Obtener tarea de la cola (Bloqueante por 5s)
            # redis-py's brpop returns tuple (queue_name, value)
            raw_data = await redis_client.brpop("astra:global:pending_recovery", timeout=5)
            
            if not raw_data: 
                continue # Timeout reached, loop again
                
            # raw_data is (b'astra:global:pending_recovery', b'{...}')
            job_json = raw_data[1]
            job = json.loads(job_json)
            
            sequence_id = job.get('sequence_id')
            session_id = job.get('session_id')
            tenant_id = job.get('tenant_id')
            s3_url = job.get('s3_url')

            logger.info(f"🔄 Intentando recuperar bloque {sequence_id} de sesión {session_id}")

            try:
                # 2. Descargar audio de S3 y re-enviar a CORE
                audio_content = await download_from_s3(s3_url)
                
                async with httpx.AsyncClient() as client:
                    files = {"file": ("recovered.wav", audio_content, "audio/wav")}
                    data = {"tenant_id": tenant_id}
                    
                    # El worker también usa el ResilienceManager pero con cuidado
                    # Si el CB está abierto, fallará rápido y re-encolará
                    response = await ResilienceManager.call_core(
                        client, 
                        core_url, 
                        files=files, 
                        data=data, 
                        timeout=settings.AI_TIMEOUT_SECONDS
                    )
                    
                    if response.status_code == 200 or response.status_code == 201:
                        # 3. Actualizar Redis con el texto recuperado
                        result = response.json()
                        final_text = result.get("clean_text") or result.get("raw_text") or ""
                        
                        await store.update_block_status(session_id, sequence_id, {
                            "status": "COMPLETED", 
                            "clean_text": final_text,
                            "raw_text": final_text,
                            "recovered_at": datetime.utcnow().isoformat(),
                            "is_pending": False,
                            "error_detail": None
                        })
                        logger.info(f"✅ Bloque {sequence_id} recuperado exitosamente.")
                    else:
                        raise Exception(f"Core returned {response.status_code}")
            
            except Exception as e:
                # Si falla, re-encolar al final con delay.
                logger.error(f"Fallo en recuperación: {e}. Re-encolando...")
                await asyncio.sleep(5) 
                # Push back to list (Right Push to queue or Left Push to stack? Usually queue: LPUSH is head, RPOP/BRPOP is tail. 
                # If we want to retry later, maybe RPUSH? Or LPUSH to retry immediately?
                # Prompt says: "re-encolando..." and typically we want breadth-first so push to head (LPUSH) if we pop from tail (RPOP)?
                # Or if queue is LIFO/FIFO...
                # Default queue pattern: LPUSH to add, BRPOP to remove. (LIFO stack if same end). 
                # Queue: LPUSH to add, BRPOP (from right) to remove. (FIFO).
                # To retry, let's LPUSH it back.
                await redis_client.lpush("astra:global:pending_recovery", job_json)
                
        except asyncio.CancelledError:
            logger.info("Worker shutting down...")
            break
        except Exception as e:
            logger.error(f"Critical worker error: {e}")
            await asyncio.sleep(5)
