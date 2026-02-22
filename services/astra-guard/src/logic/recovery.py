import json
import logging
import zipstream  # Requiere instalar zipstream-ng
from datetime import datetime
from typing import Generator, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from src.db.models import Snapshot, AuditLog
from src.infrastructure.storage_gateway import StorageGateway

logger = logging.getLogger(__name__)

class RecoveryEngine:
    def __init__(self, db: Session):
        self.db = db
        self.storage = StorageGateway()

    def get_snapshot_at_time(self, session_id: str, target_timestamp: datetime, tenant_id: str) -> Optional[Snapshot]:
        """
        [GRD-05.1] Busca el snapshot válido más cercano (hacia atrás) al timestamp dado.
        Esto permite "viajar en el tiempo" para ver cómo era el documento en esa fecha.
        """
        return self.db.query(Snapshot).filter(
            Snapshot.session_id == session_id,
            Snapshot.tenant_id == tenant_id,
            Snapshot.created_at <= target_timestamp
        ).order_by(desc(Snapshot.created_at)).first()

    def _build_genealogy(self, current_snapshot: Snapshot) -> list[dict]:
        """
        Reconstruye la cadena de versiones (V1 <- V2 <- V3) siguiendo los parent_id.
        """
        chain = []
        pointer = current_snapshot
        
        while pointer:
            chain.append({
                "version": pointer.version_number,
                "snapshot_id": str(pointer.id),
                "timestamp": pointer.created_at.isoformat(),
                "hash": pointer.root_hash,
                "is_current": pointer.id == current_snapshot.id
            })
            
            if pointer.parent_snapshot_id:
                # Nota: Snapshot.id es UUID en el modelo db/models.py
                pointer = self.db.query(Snapshot).get(pointer.parent_snapshot_id)
            else:
                pointer = None
        
        # Ordenar cronológicamente (V1 primero)
        return sorted(chain, key=lambda x: x['version'])

    def generate_evidence_package(
        self, 
        snapshot: Snapshot, 
        include_audio: bool = False
    ) -> Generator[bytes, None, None]:
        """
        [GRD-05.2] Genera un stream ZIP con el documento, el audio (opcional) y el manifiesto.
        """
        
        # 1. Validar integridad física en WORM antes de proceder
        if not self.storage.verify_object_integrity(snapshot.artifact_url, snapshot.s3_version_id):
            raise RuntimeError("INTEGRITY_BREACH: El archivo físico en la bóveda no coincide con el registro.")

        # 2. Construir Manifiesto de Auditoría JSON
        genealogy = self._build_genealogy(snapshot)
        manifest = {
            "evidence_id": str(snapshot.id),
            "tenant_id": snapshot.tenant_id,
            "session_id": snapshot.session_id,
            "integrity_hash": snapshot.root_hash,
            "sealed_at": snapshot.created_at.isoformat(),
            "chain_of_custody": genealogy,
            "legal_notice": "Este paquete es evidencia digital inmutable generada por ASTRA-GUARD.",
            "includes_audio": include_audio
        }
        
        # 3. Iniciar Stream ZIP
        # Usamos zipstream para no cargar todo en memoria
        zs = zipstream.ZipFile(mode='w', compression=zipstream.ZIP_DEFLATED)

        # A. Agregar Documento (Stream desde S3)
        doc_stream = self.storage.get_object_stream(snapshot.artifact_url, snapshot.s3_version_id)
        zs.write_iter(f"acta_v{snapshot.version_number}.docx", doc_stream)

        # B. Agregar Manifiesto JSON
        zs.write_iter("manifest_auditoria.json", [json.dumps(manifest, indent=2).encode('utf-8')])

        # Generar el ZIP
        for chunk in zs:
            yield chunk

        # Registrar acceso
        self._log_access(snapshot, "RECOVERY_EXPORT")

    def _log_access(self, snapshot, action):
        log = AuditLog(
            tenant_id=snapshot.tenant_id,
            snapshot_id=snapshot.id,
            actor_id="SYSTEM_RECOVERY",
            action=action,
            status="SUCCESS"
        )
        self.db.add(log)
        self.db.commit()
