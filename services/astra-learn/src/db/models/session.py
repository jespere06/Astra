import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON
from src.db.database import Base

class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, index=True, nullable=False)
    name = Column(String, nullable=False)
    rows = Column(JSON, default=list)  # Almacena el estado de la grilla (URLs, estado, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
