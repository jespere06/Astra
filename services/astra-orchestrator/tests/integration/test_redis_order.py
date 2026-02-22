import pytest
import asyncio
from src.models.session_store import SessionStore
from src.infrastructure.redis_client import get_redis

@pytest.mark.asyncio
async def test_zset_ordering():
    redis = get_redis()
    store = SessionStore(redis)
    sid = "test-session-123"

    # Insertar en desorden
    await store.append_block(sid, 3, {"text": "Tercero"})
    await store.append_block(sid, 1, {"text": "Primero"})
    await store.append_block(sid, 2, {"text": "Segundo"})

    # Recuperar
    data = await store.get_full_session_data(sid)
    
    # Validar orden lógico
    assert data["blocks"][0]["text"] == "Primero"
    assert data["blocks"][1]["text"] == "Segundo"
    assert data["blocks"][2]["text"] == "Tercero"
    
    print("✅ Prueba de ordenamiento ZSET: PASADA")
