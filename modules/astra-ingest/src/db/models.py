import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Enum, ForeignKey, Text, Boolean, Float, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class JobStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"

class MappingOrigin(str, enum.Enum):
    AUTO = "AUTO"
    HUMAN = "HUMAN"

class EntityType(str, enum.Enum):
    TEMPLATE = "TEMPLATE"
    ASSET = "ASSET"

class AssetType(str, enum.Enum):
    IMAGE = "IMAGE"
    MEDIA = "MEDIA"

class IngestJob(Base):
    __tablename__ = "ingest_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    status = Column(Enum(JobStatus), default=JobStatus.QUEUED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    error_log = Column(Text, nullable=True)

class Skeleton(Base):
    __tablename__ = "skeletons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    s3_path = Column(String, nullable=False) # JSON metadata path
    ooxml_path = Column(String, nullable=True) # Path al XML/DOCX físico del esqueleto
    
    # Nuevo campo para Version Pinning (Fase 1-T13)
    s3_version_id = Column(String, nullable=True) 
    
    # Estructura del documento (Sections, Block IDs)
    meta_xml = Column(JSONB, nullable=False) 
    # Hash SHA256 del contenido estructural para evitar duplicados
    content_hash = Column(String, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class TableTemplate(Base):
    """
    Almacena las filas molde de las tablas dinámicas detectadas.
    """
    __tablename__ = "table_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    storage_path = Column(String, nullable=False) # s3://astra-templates/tables/{id}.xml
    created_at = Column(DateTime, default=datetime.utcnow)

class StyleMap(Base):
    __tablename__ = "style_maps"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, unique=True) # Un mapa activo por tenant
    # Mapeo: {"Estilo Cliente": "ASTRA_HEADING_1"}
    mapping_dict = Column(JSONB, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Asset(Base):
    __tablename__ = "assets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    asset_type = Column(Enum(AssetType), nullable=False)
    # Hash perceptual para deduplicación (pHash)
    p_hash = Column(String, nullable=False, index=True)
    storage_url = Column(String, nullable=False)
    original_filename = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Template(Base):
    __tablename__ = "templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    
    # Hash del contenido estático de la plantilla para evitar duplicados exactos
    structure_hash = Column(String, nullable=False, index=True)
    
    # Ruta en S3/MinIO donde se guarda el XML físico (.xml)
    storage_path = Column(String, nullable=False)
    
    # Metadatos sobre las variables detectadas (ej: ["VAR_0", "VAR_1"])
    variables_metadata = Column(JSONB, nullable=True)
    
    # ID del cluster que originó esta plantilla (trazabilidad)
    cluster_source_id = Column(String, nullable=True)
    
    # Flag para diferenciar texto 100% estático de plantillas con variables
    is_boilerplate = Column(Boolean, default=False)
    is_seed = Column(Boolean, default=False)
    seed_label = Column(String, nullable=True) # Nombre de la sección del manual

    # --- NUEVA COLUMNA para UX ---
    # Texto base (patrón) para mostrar en el Dashboard de mapeo
    preview_text = Column(Text, nullable=True)

    # Etiqueta semántica asignada (ej. ACTA_APERTURA)
    user_label = Column(String, nullable=True, index=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class SeedAnchor(Base):
    __tablename__ = "seed_anchors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    text = Column(String, nullable=False)
    vector = Column(JSONB, nullable=True) # Almacenamos el embedding como JSONB para portabilidad
    label = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class ZoneMapping(Base):
    __tablename__ = "zone_mappings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    
    # Relación con la plantilla
    template_id = Column(UUID(as_uuid=True), ForeignKey("templates.id"), nullable=False, unique=True)
    
    # Zona asignada (HEADER, BODY, FOOTER, ANEXOS)
    zone_id = Column(String, nullable=False, default="ZONE_BODY")
    
    # Estadísticas para debugging y re-evaluación
    position_stats = Column(JSONB, nullable=False)
    
    # Nivel de confianza del sistema (0.0 a 1.0)
    confidence_score = Column(Float, default=0.0)
    
    # Origen del mapeo
    origin = Column(Enum(MappingOrigin), default=MappingOrigin.AUTO)
    
    # Candado
    is_locked = Column(Boolean, default=False)
    
    # Nuevo campo para control de sincronización (Fase 1-T12)
    synced_at = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class LabelCatalog(Base):
    """
    Diccionario histórico que vincula un hash estructural con un nombre semántico.
    Permite que futuros descubrimientos hereden el nombre automáticamente.
    """
    __tablename__ = "label_catalog"
    __table_args__ = (
        UniqueConstraint('tenant_id', 'entity_hash', 'entity_type', name='uq_tenant_hash_type'),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=False, index=True)
    
    entity_type = Column(Enum(EntityType), nullable=False)
    entity_hash = Column(String, nullable=False, index=True)
    label_name = Column(String, nullable=False)
    
    created_by = Column(String, nullable=True) # User ID o 'SYSTEM'
    created_at = Column(DateTime, default=datetime.utcnow)

class TenantConfig(Base):
    """
    Configuración específica del inquilino y su diccionario de contexto.
    """
    __tablename__ = "tenant_configs"

    tenant_id = Column(String, primary_key=True, index=True)
    
    # Diccionario de entidades descubiertas (JSONB)
    # Ej: {"Jhon": "John", "Concejal Perez": "Honorable Concejal Pérez"}
    entities_dictionary = Column(JSONB, nullable=False, default={})
    
    # Configuración de estilos y zonas (opcional aquí si ya está en otras tablas, 
    # pero útil para centralizar)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)