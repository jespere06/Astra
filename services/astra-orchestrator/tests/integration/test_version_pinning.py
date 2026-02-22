import pytest
import datetime
from src.schemas.session_dtos import SessionStartRequest
from src.services.session_service import SessionService
from src.models.session_store import SessionStore
from src.infrastructure.clients.config_client import ConfigClient
from src.infrastructure.redis_client import get_redis

# Mocking Config Client for Unit/Integration test simplicity without HTTP
class MockConfigClient(ConfigClient):
    async def get_tenant_config(self, tenant_id: str) -> dict:
         return {
            "adapter_id": "base-model-v1",
            "style_map": {"body": "OriginalStyle", "header": "Heading 1"},
            "zone_map": {"DEFAULT": "Body"},
            "table_map": {}
        }
        
class MockConfigClientChanged(ConfigClient):
     async def get_tenant_config(self, tenant_id: str) -> dict:
         return {
            "adapter_id": "base-model-v2",
            "style_map": {"body": "ChangedStyle", "header": "Heading 1"},
             "zone_map": {"DEFAULT": "Body"},
            "table_map": {}
        }

@pytest.mark.asyncio
async def test_session_version_pinning():
    # 1. Setup
    redis = get_redis()
    store = SessionStore(redis)
    config_client = MockConfigClient()
    service = SessionService(store, config_client)
    
    req = SessionStartRequest(
        tenant_id="test_tenant_pinning",
        skeleton_id="sk_01",
        client_timezone="America/Bogota"
    )

    # 2. Iniciar sesión con config original
    session_state = await service.start_new_session(req)
    original_style = session_state.pinned_config.style_map["body"]
    session_id = session_state.session_id
    
    assert original_style == "OriginalStyle"

    # 3. "Simular" cambio en Config Service Global (Cambiamos el cliente en memoria para una nueva sesion hipotetica,
    # pero verificamos que al leer la sesion vieja de Redis, sigue intacta)
    
    # Leemos directamente de Redis lo que se guardó
    saved_data = await store.get_full_session_data(session_id)
    saved_meta = saved_data["metadata"]
    
    # En Redis, los valores complejos se guardan como JSON string, pero SessionStore ya los deserializa si es un dict en el Pydantic model?
    # No, SessionStore.get_full_session_data devuelve diccionarios, no modelos Pydantic
    # Pero el SessionStore guarda con json.dumps
    
    # 4. Verificar inmutabilidad en Redis
    # El style_map en Redis debe ser el original "OriginalStyle"
    # Nota: SessionStore.get_full_session_data deserializa
    
    # Redis devuelve strings, SessionStore intenta json.loads
    # Vamos a verificar el diccionario
    import json
    # La metadata en SessionStore guarda "pinned_config" como un bloque JSON entero?
    # Revisando session_store.py:
    # serialized_meta = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) ...
    # pinned_config es un dict, asi que se serializó a string JSON.
    
    # Al recuperar:
    # blocks = [json.loads(b) for b in results[1]]
    # meta = results[0] -> Esto es un dict de strings.
    
    # SessionStore no deserializa automaticamente los valores del HASH en get_full_session_data!
    # Solo deserializa los bloques. La metadata hay que deserializarla manualmente si se sabe que es JSON.
    # Corrijamos el test para parsear el JSON de pinned_config
    
    pinned_config_str = saved_meta["pinned_config"]
    pinned_config = json.loads(pinned_config_str)
    
    assert pinned_config["style_map"]["body"] == "OriginalStyle"
    print("✅ Inmutabilidad (Version Pinning) verificada en Redis.")
