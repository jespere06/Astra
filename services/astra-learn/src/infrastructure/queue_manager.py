import logging
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, update

from src.db.models.queue import TrainingQueue, QueueStatus

logger = logging.getLogger(__name__)

class QueueManager:
    def __init__(self, db: Session):
        self.db = db

    def enqueue_example(self, tenant_id: str, data: Dict) -> int:
        """Inserta un ejemplo y retorna el conteo actual pendiente."""
        item = TrainingQueue(tenant_id=tenant_id, data_json=data)
        self.db.add(item)
        self.db.commit()
        
        # Retornar conteo rápido para logging
        return self.db.query(func.count(TrainingQueue.id)).filter(
            TrainingQueue.tenant_id == tenant_id,
            TrainingQueue.status == QueueStatus.PENDING
        ).scalar()

    def get_pending_stats(self, tenant_id: str) -> Tuple[int, Optional[datetime]]:
        """Retorna (cantidad_pendiente, fecha_mas_antigua)."""
        count = self.db.query(func.count(TrainingQueue.id)).filter(
            TrainingQueue.tenant_id == tenant_id,
            TrainingQueue.status == QueueStatus.PENDING
        ).scalar()

        if count == 0:
            return 0, None

        oldest = self.db.query(func.min(TrainingQueue.created_at)).filter(
            TrainingQueue.tenant_id == tenant_id,
            TrainingQueue.status == QueueStatus.PENDING
        ).scalar()

        return count, oldest

    def checkout_batch(self, tenant_id: str, job_id: str, limit: int = 1000) -> List[Dict]:
        """
        Marca N registros como PROCESSING atómicamente y los retorna.
        Usa 'SELECT FOR UPDATE SKIP LOCKED' para concurrencia segura.
        """
        # 1. Seleccionar IDs
        subquery = self.db.query(TrainingQueue.id).filter(
            TrainingQueue.tenant_id == tenant_id,
            TrainingQueue.status == QueueStatus.PENDING
        ).limit(limit).with_for_update(skip_locked=True)

        # 2. Actualizar estado
        stmt = update(TrainingQueue).where(
            TrainingQueue.id.in_(subquery)
        ).values(
            status=QueueStatus.PROCESSING,
            job_id=job_id,
            processed_at=datetime.utcnow()
        ).returning(TrainingQueue.data_json)

        result = self.db.execute(stmt)
        self.db.commit()
        
        rows = [row[0] for row in result.fetchall()]
        logger.info(f"Checkout de {len(rows)} ejemplos para Tenant {tenant_id} (Job: {job_id})")
        return rows
