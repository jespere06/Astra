import grpc
import logging

try:
    from src.generated import session_service_pb2, session_service_pb2_grpc, astra_models_pb2
except ImportError:
    # Fallback to mocks for development if protos are not compiled
    from src.generated import session_mocks as session_service_pb2_grpc
    # Need to mock other modules too if we want full import success without generation
    session_service_pb2 = None
    astra_models_pb2 = None

from src.services.session_service import SessionService
from src.services.processor import IngestProcessor
from src.services.finalizer import SessionFinalizer
from src.services.orchestration_service import OrchestrationService
from src.schemas.session_dtos import SessionStartRequest, SessionContextUpdate
from src.infrastructure.redis_client import get_redis
from src.infrastructure.redis_lock import SessionLock
from src.models.session_store import SessionStore
from src.infrastructure.clients.config_client import ConfigClient
from src.infrastructure.storage_service import StorageService

logger = logging.getLogger(__name__)

# Inherit from Generated Servicer or Object (Mock)
ParentClass = session_service_pb2_grpc.SessionOrchestratorServicer if hasattr(session_service_pb2_grpc, 'SessionOrchestratorServicer') else object

class OrchestratorServicer(ParentClass):
    
    def __init__(self):
        # Inicialización manual de dependencias para el contexto gRPC
        self.redis = get_redis()
        self.store = SessionStore(self.redis)
        self.config_client = ConfigClient()
        self.storage = StorageService()
        
        self.session_service = SessionService(self.store, self.config_client)
        self.processor = IngestProcessor(self.store, self.storage)
        self.finalizer = SessionFinalizer(self.store, self.storage)

    async def StartSession(self, request, context):
        try:
            dto = SessionStartRequest(
                tenant_id=request.tenant_id,
                skeleton_id=request.skeleton_id,
                client_timezone=request.client_timezone,
                metadata=dict(request.metadata)
            )
            state = await self.session_service.start_new_session(dto)
            
            # Mapeo a Proto
            if astra_models_pb2:
                return astra_models_pb2.SessionContext(
                    tenant_id=state.tenant_id,
                    session_id=state.session_id,
                    skeleton_id=state.skeleton_id,
                    client_timezone=state.client_timezone
                )
        except Exception as e:
            logger.error(f"gRPC StartSession Error: {e}")
            await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def UpdateContext(self, request, context):
        try:
            dto = SessionContextUpdate(
                current_speaker_id=request.current_speaker_id,
                topic=request.topic,
                is_restricted=request.is_restricted
            )
            updated = await self.session_service.update_context(request.session_id, dto)
            
            if astra_models_pb2:
                return astra_models_pb2.SessionContext(
                    session_id=request.session_id,
                    tenant_id="LOOKUP_NEEDED" 
                )
        except Exception as e:
             await context.abort(grpc.StatusCode.INTERNAL, str(e))

    async def StreamAudio(self, request_iterator, context):
        """
        Maneja el flujo continuo de audio.
        """
        try:
            async for chunk in request_iterator:
                if not chunk.session_id:
                    continue

                # Procesamiento
                try:
                    block_id = await self.processor.process_chunk(
                        session_id=chunk.session_id,
                        sequence_id=chunk.sequence_id,
                        audio_content=chunk.audio_data
                    )
                    
                    if session_service_pb2 and astra_models_pb2:
                        yield session_service_pb2.ProcessResult(
                            block_id=block_id,
                            sequence_id=chunk.sequence_id,
                            status=astra_models_pb2.STATUS_PROCESSING, 
                            intent_detected="PENDING"
                        )
                except Exception as proc_e:
                    logger.error(f"Error processing chunk {chunk.sequence_id}: {proc_e}")
                    if session_service_pb2 and astra_models_pb2:
                        yield session_service_pb2.ProcessResult(
                            sequence_id=chunk.sequence_id,
                            status=astra_models_pb2.STATUS_FAILED,
                            error_message=str(proc_e)
                        )

        except Exception as e:
            logger.error(f"Stream interrupted: {e}")
            await context.abort(grpc.StatusCode.UNKNOWN, "Stream Error")

    async def FinalizeSession(self, request, context):
        session_id = request.session_id
        lock = SessionLock(self.redis)

        if not await lock.acquire(session_id):
            await context.abort(grpc.StatusCode.ABORTED, "Finalization already in progress")

        try:
            # 1. Check Draining
            if await self.finalizer.check_draining_status(session_id):
                await context.abort(grpc.StatusCode.FAILED_PRECONDITION, "Session is draining (processing pending blocks)")

            # 2. Build
            payload = await self.finalizer.prepare_payload(session_id)
            result = await OrchestrationService.finalize_and_seal(payload)
            
            # 3. Close
            await self.store.update_session_context(session_id, {"status": "CLOSED"})
            
            if session_service_pb2:
                return session_service_pb2.FinalizeResp(
                    download_url=result.get("download_url"),
                    integrity_hash=result.get("integrity_hash"),
                    status="COMPLETED"
                )

        except Exception as e:
            logger.error(f"Finalize Error: {e}")
            await context.abort(grpc.StatusCode.INTERNAL, str(e))
        finally:
            await lock.release(session_id)
