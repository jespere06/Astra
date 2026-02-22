from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from src.db.models import StyleMap
import json

class StyleMapRepository:
    def __init__(self, db: Session):
        self.db = db

    def upsert_mapping(self, tenant_id: str, mapping: dict):
        """
        Inserta o actualiza el mapa de estilos para un tenant.
        Utiliza UPSERT de Postgres para garantizar idempotencia.
        """
        stmt = insert(StyleMap).values(
            tenant_id=tenant_id,
            mapping_dict=mapping
        ).on_conflict_do_update(
            index_elements=['tenant_id'],
            set_={'mapping_dict': mapping, 'updated_at': func.now()}
        )
        
        self.db.execute(stmt)
        self.db.commit()

    def get_mapping(self, tenant_id: str) -> dict:
        result = self.db.query(StyleMap).filter(StyleMap.tenant_id == tenant_id).first()
        return result.mapping_dict if result else {}