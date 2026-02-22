import json
import logging
import os
import redis
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

class ModelPromoter:
    """
    Gestiona la promoción de modelos aprobados hacia producción.
    """
    def __init__(self):
        # Conexión a Redis para Pub/Sub
        self.redis = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://redis:6379/0"), decode_responses=True)
        # URL del servicio de configuración de Tenants
        self.config_service_url = os.getenv("TENANT_CONFIG_URL", "http://tenant-config-service:8080")

    def promote(self, tenant_id: str, adapter_s3_uri: str, version_id: str):
        logger.info(f"Promoviendo modelo {version_id} para tenant {tenant_id}...")
        
        try:
            # 1. Actualizar "Single Source of Truth" (DB de Configuración)
            self._update_tenant_config(tenant_id, adapter_s3_uri)
            
            # 2. Señalización Persistente (Flag para nuevas sesiones)
            # Esto permite que el Orquestador sepa qué modelo usar al iniciar sesión
            redis_key = f"NEW_MODEL_AVAILABLE:{tenant_id}"
            self.redis.set(redis_key, adapter_s3_uri, ex=86400) # TTL 24h
            
            # 3. Notificación en Tiempo Real (Pub/Sub)
            # Esto avisa a los pods de CORE que deben precargar el modelo ya
            event_payload = {
                "event": "MODEL_UPDATED",
                "tenant_id": tenant_id,
                "s3_uri": adapter_s3_uri,
                "version": version_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            self.redis.publish("astra:events:intelligence", json.dumps(event_payload))
            
            logger.info(f"🚀 Modelo promovido exitosamente en el sistema para {tenant_id}")
            
        except Exception as e:
            logger.error(f"Fallo en promoción de modelo: {e}")
            raise e

    def _update_tenant_config(self, tenant_id: str, adapter_uri: str):
        """Llamada al microservicio de configuración para persistir el cambio."""
        url = f"{self.config_service_url}/v1/config/{tenant_id}/model"
        payload = {"active_adapter_uri": adapter_uri}
        
        try:
            response = requests.patch(url, json=payload, timeout=5.0)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Error llamando al servicio de configuración: {e}")
            raise
