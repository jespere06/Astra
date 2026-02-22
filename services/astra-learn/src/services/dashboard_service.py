from sqlalchemy.orm import Session
from src.infrastructure.queue_manager import QueueManager
from src.infrastructure.repositories.job_repo import JobRepository
from src.services.metrics_adapter import MetricsAdapter
from src.config import settings

class DashboardService:
    def __init__(self, db: Session):
        self.queue_mgr = QueueManager(db)
        self.job_repo = JobRepository(db)
        self.metrics_adapter = MetricsAdapter()

    def get_learning_status(self, tenant_id: str) -> dict:
        """
        Resumen 'Head-up Display' para el admin.
        Muestra cuánto falta para el próximo entrenamiento y el estado del último.
        """
        pending_count, oldest_date = self.queue_mgr.get_pending_stats(tenant_id)
        last_job = self.job_repo.get_last_job(tenant_id)
        
        # Calcular progreso hacia el umbral
        threshold = settings.BATCH_SIZE_THRESHOLD
        progress_pct = min(100, int((pending_count / threshold) * 100)) if threshold > 0 else 0

        return {
            "queue": {
                "pending_samples": pending_count,
                "threshold": threshold,
                "progress_percentage": progress_pct,
                "next_training_estimated": "Inmediato" if progress_pct == 100 else "Pendiente de datos"
            },
            "last_job": {
                "status": last_job.status if last_job else "NONE",
                "date": last_job.finished_at if last_job else None,
                "model_version": last_job.model_version if last_job else "v1.0 (Base)"
            }
        }

    def get_job_analytics(self, tenant_id: str, job_id: str):
        """Detalle profundo de un entrenamiento específico."""
        job = self.job_repo.get_job_by_id(job_id, tenant_id)
        if not job or not job.mlflow_run_id:
            return None
            
        return self.metrics_adapter.get_job_details(job.mlflow_run_id)
