from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, LargeBinary, Integer, Boolean
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime
import uuid

class Base(DeclarativeBase):
    pass

class Snapshot(Base):
    """
    Representa un estado inmutable de una sesión o documento en un momento dado.
    """
    __tablename__ = "snapshots"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(50), nullable=False, index=True)
    session_id = Column(String(50), nullable=False, index=True)
    
    # Hash de integridad (Merkle Root)
    root_hash = Column(String(64), nullable=False)
    
    # Referencia al storage (S3 Key)
    s3_key = Column(String(255), nullable=False)
    
    # Metadatos del snapshot (ej. version, type: 'session' | 'final_doc')
    metadata_json = Column(JSON, default=dict)
    
    # Trazabilidad
    parent_snapshot_id = Column(String(36), ForeignKey("snapshots.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Flags de cumplimiento
    is_locked = Column(Boolean, default=False)
    retention_until = Column(DateTime, nullable=True)

class MerkleNode(Base):
    """
    Almacena los nodos del árbol de Merkle para pruebas de inclusión forenses.
    """
    __tablename__ = "merkle_nodes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(36), ForeignKey("snapshots.id"), nullable=False, index=True)
    level = Column(Integer, nullable=False)
    index = Column(Integer, nullable=False)
    node_hash = Column(String(64), nullable=False)

class AuditLog(Base):
    """
    Registro forense de todas las operaciones sobre la bóveda.
    """
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String(50), nullable=False, index=True)
    operation = Column(String(50), nullable=False) # ej. 'CREATE_SNAPSHOT', 'VERIFY', 'RECOVER'
    resource_id = Column(String(100), nullable=True)
    user_id = Column(String(100), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Hash del log para encadenamiento (opcional en MVP)
    log_hash = Column(String(64), nullable=True)
    
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
