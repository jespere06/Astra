import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from .models import TenantConfig
from .schemas import TenantConfigUpdate, TenantConfigResponse
from .database import redis_client

logger = logging.getLogger(__name__)
CACHE_TTL = 3600  # 1 hora

def get_config(db: Session, tenant_id: str) -> TenantConfigResponse:
    cache_key = f"config:{tenant_id}"

    # 1. Intentar leer de Redis (Fast Path)
    if redis_client:
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logger.debug(f"Cache HIT para {tenant_id}")
            return TenantConfigResponse(**json.loads(cached_data))

    # 2. Leer de Postgres (Slow Path)
    logger.debug(f"Cache MISS para {tenant_id}, consultando DB")
    config = db.query(TenantConfig).filter(TenantConfig.tenant_id == tenant_id).first()

    if not config:
        # Retornar configuración vacía por defecto si no existe
        # Esto permite "Cold Starts" sin errores 404
        config = TenantConfig(tenant_id=tenant_id)

    # 3. Serializar y guardar en Redis
    response_model = TenantConfigResponse.model_validate(config)
    
    if redis_client:
        redis_client.setex(
            cache_key,
            CACHE_TTL,
            response_model.model_dump_json()
        )

    return response_model

def update_config(db: Session, tenant_id: str, payload: TenantConfigUpdate) -> TenantConfigResponse:
    # 1. Preparar datos para UPSERT
    update_data = payload.model_dump(exclude_unset=True)
    
    # Si viene un diccionario parcial, deberíamos hacer merge profundo, 
    # pero para este diseño asumimos que el cliente envía el mapa completo o manejamos reemplazo.
    # Aquí usamos reemplazo por simplicidad y atomicidad.
    
    stmt = insert(TenantConfig).values(
        tenant_id=tenant_id,
        **update_data
    ).on_conflict_do_update(
        index_elements=['tenant_id'],
        set_=update_data
    )
    
    db.execute(stmt)
    db.commit()

    # 2. Invalidar Caché (Write-Through / Invalidate strategy)
    if redis_client:
        cache_key = f"config:{tenant_id}"
        redis_client.delete(cache_key)
        logger.info(f"Cache invalidada para {tenant_id}")

    # 3. Retornar dato fresco
    return get_config(db, tenant_id)
