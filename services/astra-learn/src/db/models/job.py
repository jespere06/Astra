import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, Float
from sqlalchemy.dialects.postgresql import UUID
import enum
from src.db.database import Base

class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TrainingJob(Base):
    __tablename__ = "training_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, index=True, nullable=False)
    
    # IDs externos para trazabilidad
    k8s_job_name = Column(String, nullable=False)
    mlflow_run_id = Column(String, nullable=True)
    
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    
    # Métricas resumen (Snapshot para listados rápidos sin ir a MLflow)
    final_wer = Column(Float, nullable=True)
    training_loss = Column(Float, nullable=True)
    
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    
    model_version = Column(String, nullable=True) # ej: v2.1
