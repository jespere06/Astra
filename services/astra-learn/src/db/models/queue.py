import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Enum, Integer, Float
from sqlalchemy.dialects.postgresql import UUID
import enum
from src.db.database import Base

class QueueStatus(str, enum.Enum):
    PENDING = "PENDING"
    READY = "READY"
    PENDING_REVIEW = "PENDING_REVIEW"
    DISCARDED = "DISCARDED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class TrainingQueue(Base):
    __tablename__ = "training_queue"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, index=True, nullable=False)
    data_json = Column(JSON, nullable=False)  # El par {instruction, input, output}
    status = Column(Enum(QueueStatus), default=QueueStatus.PENDING, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    validation_score = Column(Float, nullable=True)
    validation_reasoning = Column(String, nullable=True)
    job_id = Column(String, nullable=True) # ID del Job de K8s que lo tomó
