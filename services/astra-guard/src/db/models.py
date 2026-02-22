import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
import enum

Base = declarative_base()

class HashAlgorithm(str, enum.Enum):
    SHA256 = "SHA-256"
    SHA512 = "SHA-512"

class Snapshot(Base):
    """
    Representa un estado inmutable de un documento o activo.
    """
    __tablename__ = "snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    
    # Referencia al archivo físico en el bucket WORM
    artifact_url = Column(String, nullable=False) # s3://astra-guard-vault/...
    s3_version_id = Column(String, nullable=False) # ID de versión de S3 para inmutabilidad estricta
    
    # Integridad Criptográfica
    root_hash = Column(String(64), nullable=False, index=True) # Merkle Root
    algorithm = Column(Enum(HashAlgorithm), default=HashAlgorithm.SHA256)
    
    # Cifrado (Envelope Encryption)
    kms_key_id = Column(String, nullable=False) # ID de la llave maestra usada
    encrypted_data_key = Column(String, nullable=False) # DEK cifrada
    
    # Linaje (Time-Travel)
    parent_snapshot_id = Column(UUID(as_uuid=True), ForeignKey("snapshots.id"), nullable=True)
    version_number = Column(Integer, default=1)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Nuevas columnas para Audio
    audio_url = Column(String, nullable=True) # s3://astra-audio-vault/...
    audio_hash = Column(String(64), nullable=True, index=True)
    audio_s3_version = Column(String, nullable=True)
    
    # Relaciones
    merkle_tree = relationship("MerkleTree", back_populates="snapshot", uselist=False)

class MerkleTree(Base):
    """
    Almacena la estructura del árbol de hash para pruebas parciales.
    Si el árbol es muy grande, se guarda el JSON completo.
    """
    __tablename__ = "merkle_trees"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("snapshots.id"), unique=True)
    
    # Estructura del árbol: { "leaves": ["hash1", "hash2"], "layers": [...] }
    tree_structure = Column(JSONB, nullable=False)
    
    snapshot = relationship("Snapshot", back_populates="merkle_tree")

class AuditLog(Base):
    """
    Bitácora forense de accesos y verificaciones (Append-Only).
    """
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    snapshot_id = Column(UUID(as_uuid=True), ForeignKey("snapshots.id"), nullable=True)
    
    actor_id = Column(String, nullable=False) # Usuario o Servicio
    action = Column(String, nullable=False) # CREATE, VERIFY, RECOVER
    
    status = Column(String, nullable=False) # SUCCESS, INTEGRITY_FAILURE
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    extra_metadata = Column("metadata", JSONB, nullable=True)
