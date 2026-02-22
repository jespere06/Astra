import logging
import re
from typing import List, Optional
from sqlalchemy.orm import Session
from src.db.models import LabelCatalog, Template, EntityType

logger = logging.getLogger(__name__)

class LabelManager:
    def __init__(self, db: Session):
        self.db = db

    def _normalize_label(self, label: str) -> str:
        """Convierte 'Apertura de sesión' a 'APERTURA_DE_SESION'."""
        label = label.strip().upper()
        # Reemplazar espacios y caracteres no alfanuméricos con guion bajo
        label = re.sub(r'[^A-Z0-9]+', '_', label)
        # Eliminar guiones bajos múltiples
        label = re.sub(r'_+', '_', label)
        return label.strip('_')

    def assign_label(self, tenant_id: str, entity_hash: str, label_name: str, entity_type: EntityType = EntityType.TEMPLATE, user_id: str = "ADMIN_CLI"):
        """
        Asigna una etiqueta a un hash y actualiza retrospectivamente las entidades existentes.
        """
        normalized_label = self._normalize_label(label_name)
        
        # 1. Upsert en el Catálogo
        catalog_entry = self.db.query(LabelCatalog).filter_by(
            tenant_id=tenant_id,
            entity_hash=entity_hash,
            entity_type=entity_type
        ).first()

        if catalog_entry:
            catalog_entry.label_name = normalized_label
            catalog_entry.created_by = user_id
            logger.info(f"Actualizando etiqueta para hash {entity_hash[:8]} -> {normalized_label}")
        else:
            new_entry = LabelCatalog(
                tenant_id=tenant_id,
                entity_type=entity_type,
                entity_hash=entity_hash,
                label_name=normalized_label,
                created_by=user_id
            )
            self.db.add(new_entry)
            logger.info(f"Creando nueva etiqueta para hash {entity_hash[:8]} -> {normalized_label}")

        # 2. Propagación Retrospectiva (Solo para Templates por ahora)
        if entity_type == EntityType.TEMPLATE:
            templates = self.db.query(Template).filter_by(
                tenant_id=tenant_id,
                structure_hash=entity_hash
            ).all()
            
            for tmpl in templates:
                tmpl.user_label = normalized_label
            
            logger.info(f"Etiqueta propagada a {len(templates)} templates existentes.")

        self.db.commit()
        return normalized_label

    def get_label_for_hash(self, tenant_id: str, entity_hash: str, entity_type: EntityType) -> Optional[str]:
        """Busca si existe una etiqueta predefinida para este hash."""
        entry = self.db.query(LabelCatalog).filter_by(
            tenant_id=tenant_id,
            entity_hash=entity_hash,
            entity_type=entity_type
        ).first()
        return entry.label_name if entry else None

    def get_unlabeled_templates(self, tenant_id: str, limit: int = 10) -> List[Template]:
        """Retorna templates que no tienen user_label ni son seeds."""
        return self.db.query(Template).filter(
            Template.tenant_id == tenant_id,
            Template.user_label == None,
            Template.is_seed == False
        ).order_by(Template.created_at.desc()).limit(limit).all()