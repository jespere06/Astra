from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Tuple, Optional
from src.db.models.job import TrainingJob

class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_jobs_by_tenant(self, tenant_id: str, skip: int = 0, limit: int = 10) -> Tuple[List[TrainingJob], int]:
        """
        Retorna lista paginada de jobs y el total.
        """
        query = self.db.query(TrainingJob).filter(TrainingJob.tenant_id == tenant_id)
        
        total = query.count()
        items = query.order_by(desc(TrainingJob.started_at)).offset(skip).limit(limit).all()
        
        return items, total

    def get_job_by_id(self, job_id: str, tenant_id: str) -> Optional[TrainingJob]:
        """Busca un job validando propiedad del tenant."""
        return self.db.query(TrainingJob).filter(
            TrainingJob.id == job_id,
            TrainingJob.tenant_id == tenant_id
        ).first()

    def get_last_job(self, tenant_id: str) -> Optional[TrainingJob]:
        return self.db.query(TrainingJob)\
            .filter(TrainingJob.tenant_id == tenant_id)\
            .order_by(desc(TrainingJob.started_at))\
            .first()
