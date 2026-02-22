import logging
from datetime import datetime, timezone
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from src.db.models import ZoneMapping
from src.infrastructure.clients.config_service import ConfigServiceClient

logger = logging.getLogger(__name__)

class SyncManager:
    """
    Gestor de sincronización de estado entre Ingesta y Configuración Central.
    """

    def __init__(self, db: Session, client: ConfigServiceClient):
        self.db = db
        self.client = client

    def get_pending_mappings(self, tenant_id: str) -> List[ZoneMapping]:
        """
        Obtiene los mapeos que han sido validados (locked) pero no sincronizados,
        o que han sido actualizados después de su última sincronización.
        """
        return self.db.query(ZoneMapping).filter(
            ZoneMapping.tenant_id == tenant_id,
            ZoneMapping.is_locked == True,  # Solo sincronizar lo validado por humanos/reglas firmes
            or_(
                ZoneMapping.synced_at == None,
                ZoneMapping.updated_at > ZoneMapping.synced_at
            )
        ).all()

    def sync_tenant_mappings(self, tenant_id: str) -> int:
        """
        Ejecuta el ciclo de sincronización para un tenant específico.
        
        Flow:
        1. Buscar pendientes.
        2. Transformar a DTO externo.
        3. Enviar a API externa.
        4. Actualizar estado local (synced_at) si éxito.
        
        Returns:
            Número de registros sincronizados.
        """
        logger.info(f"🔄 Iniciando sincronización para tenant: {tenant_id}")

        # 1. Selección
        pending_records = self.get_pending_mappings(tenant_id)
        
        if not pending_records:
            logger.info(f"✅ Tenant {tenant_id}: No hay cambios pendientes de sincronización.")
            return 0

        # 2. Transformación
        # Convertimos el modelo interno DB al contrato JSON del Config Service
        payload_items = []
        for record in pending_records:
            payload_items.append({
                "template_id": str(record.template_id),
                "target_placeholder": record.zone_id,
                "confidence": record.confidence_score,
                "is_manual": record.origin == "HUMAN"
            })

        payload = {"mappings": payload_items}

        # 3. Propagación
        try:
            logger.debug(f"Enviando {len(payload_items)} mapeos a Config Service...")
            success = self.client.update_zone_mappings(tenant_id, payload)

            if not success:
                logger.error(f"Fallo en la respuesta del Config Service para {tenant_id}")
                return 0

            # 4. Confirmación (Actualización de Estado)
            sync_timestamp = datetime.now(timezone.utc)
            for record in pending_records:
                record.synced_at = sync_timestamp
            
            self.db.commit()
            logger.info(f"✅ Sincronización exitosa: {len(pending_records)} registros actualizados para {tenant_id}.")
            return len(pending_records)

        except Exception as e:
            self.db.rollback()
            logger.error(f"❌ Error crítico sincronizando tenant {tenant_id}: {str(e)}")
            # En un sistema de colas (Celery/Arq), aquí se relanzaría la excepción 
            # para activar el mecanismo de retries.
            raise e