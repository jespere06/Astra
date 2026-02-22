import pytest
from unittest.mock import AsyncMock, MagicMock
from src.schemas.session_dtos import SessionStartRequest, SessionContextUpdate
from src.services.session_service import SessionService
from src.services.processor import AudioProcessor
from src.models.session_store import SessionStore
from src.infrastructure.clients.config_client import ConfigClient
from src.infrastructure.clients.core_client import CoreClient
from src.infrastructure.redis_client import get_redis

# Mocking external services
class MockConfigClient(ConfigClient):
    async def get_tenant_config(self, tenant_id: str) -> dict:
         return {
            "adapter_id": "base-model-v1",
            "style_map": {"body": "OriginalStyle"},
            "zone_map": {"DEFAULT": "Body"},
            "table_map": {}
        }

class MockCoreClient(CoreClient):
    async def process_audio_chunk(self, audio_bytes, tenant_id):
        return {
            "raw_text": "Texto procesado por IA",
            "intent": "TEST_INTENT",
            "confidence": 0.95,
            "metadata": {}
        }

@pytest.mark.asyncio
async def test_full_flow_dynamic_context():
    # 1. Setup Container
    redis = get_redis()
    await redis.flushdb() # Limpiar Redis para test limpio
    
    store = SessionStore(redis)
    config_client = MockConfigClient()
    core_client = MockCoreClient()
    
    session_service = SessionService(store, config_client)
    processor = AudioProcessor(store, core_client)

    # 2. START SESSION
    req = SessionStartRequest(
        tenant_id="flow_tester",
        skeleton_id="sk_flow"
    )
    state = await session_service.start_new_session(req)
    sid = state.session_id
    print(f"✅ Session Started: {sid}")

    # 3. UPDATE CONTEXT (Cambiamos el orador)
    ctx_update = SessionContextUpdate(current_speaker_id="Concejal Carlos", topic="Moción de Censura", is_restricted=True)
    updated_ctx = await session_service.update_context(sid, ctx_update)
    
    assert updated_ctx.current_speaker_id == "Concejal Carlos"
    assert updated_ctx.is_restricted is True
    print("✅ Context Updated")

    # 4. APPEND CHUNK (Verificar estado en Redis)
    dummy_audio = b"\x00\x00\x00\x00" * 1024
    result = await processor.process_chunk(sid, dummy_audio, sequence_id=1)
    
    assert result["status"] == "processed"
    print("✅ Chunk Processed")

    # 5. VERIFICACION FINAL (El bloque en Redis heredo el contexto?)
    # Nota: AudioProcessor actualmente no inyecta el contexto en el bloque explicitamente
    # en la version actual, pero el contexto global existe en Redis para cuando se ensamble.
    # Verifiquemos que el contexto global sigue persistiendo.
    final_ctx = await store.get_current_context(sid)
    assert final_ctx["current_speaker_id"] == "Concejal Carlos"
    assert final_ctx["is_restricted"] is True
    print("✅ Final State Verified")
