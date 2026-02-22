from sqlalchemy.orm import Session
from src.db.models import IntegrityManifest

class ManifestRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_manifest(self, tenant_id: str, session_id: str, file_hash: str, signature: str, builder_version: str = "1.0"):
        manifest = IntegrityManifest(
            tenant_id=tenant_id,
            session_id=session_id,
            integrity_hash=file_hash,
            signature=signature,
            builder_version=builder_version
        )
        self.db.add(manifest)
        self.db.commit()
        self.db.refresh(manifest)
        return manifest

    def get_by_hash(self, integrity_hash: str):
        return self.db.query(IntegrityManifest).filter(
            IntegrityManifest.integrity_hash == integrity_hash
        ).first()
