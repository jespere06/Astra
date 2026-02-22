from sqlalchemy import Column, String, DateTime, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

Base = declarative_base()

class TenantConfig(Base):
    """
    Representa el 'Snapshot' de configuración activo para un inquilino.
    Optimizado para lectura rápida (O(1)) por el Orquestador.
    """
    __tablename__ = "tenant_configs"

    # El tenant_id es la PK natural (ej: "CONCEJO_MANIZALES")
    tenant_id = Column(String, primary_key=True, index=True)
    
    # ID del Skeleton activo (puntero a S3/DB de Ingest)
    active_skeleton_id = Column(String, nullable=True)
    
    # Mapeo de Estilos: { "Estilo Original": "ASTRA_STYLE_ID" }
    style_map = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    
    # Mapeo de Zonas: { "template_uuid": "ZONE_HEADER" }
    zone_map = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    
    # Mapeo de Tablas Dinámicas: { "intent_votacion": "TBL_UUID_EN_DOCX" }
    table_map = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(String, default=lambda: str(uuid.uuid4())) # Para control de concurrencia
