from sqlalchemy import Column, String, Integer, ForeignKey, JSON, DateTime
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.sql import func
import uuid

Base = declarative_base()

class Skeleton(Base):
    __tablename__ = "skeletons"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, index=True)
    s3_path = Column(String)
    original_filename = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relación simple para demostración
    assets = relationship("Asset", back_populates="skeleton")

class Asset(Base):
    __tablename__ = "assets"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    skeleton_id = Column(String, ForeignKey("skeletons.id"))
    p_hash = Column(String, index=True)
    original_name = Column(String)
    s3_path = Column(String)
    content_type = Column(String)
    
    skeleton = relationship("Skeleton", back_populates="assets")
