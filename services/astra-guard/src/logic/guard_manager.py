import logging
import uuid
import boto3
from datetime import datetime
from fastapi import UploadFile
from sqlalchemy.orm import Session
from botocore.config import Config

from src.config import settings
from src.db.models import Snapshot, MerkleTree, AuditLog
from src.crypto.normalizer import OOXMLNormalizer
from src.crypto.merkle import MerkleEngine
from src.crypto.manager import EncryptionManager
from src.infrastructure.kms_client import AWSKMSDriver

logger = logging.getLogger(__name__)

class GuardManager:
    def __init__(self, db: Session):
        self.db = db
        # Inicializar componentes de criptografía
        self.kms_driver = AWSKMSDriver()
        self.crypto_manager = EncryptionManager(self.kms_driver)
        
        # Cliente S3 para WORM Storage
        self.s3 = boto3.client(
            's3',
            region_name=settings.AWS_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL, # Para local/minio
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )
        self.vault_bucket = settings.GUARD_VAULT_BUCKET

    async def seal_artifact(
        self, 
        file: UploadFile, 
        tenant_id: str, 
        session_id: str,
        metadata: dict
    ) -> Snapshot:
        """
        Ejecuta el flujo de sellado:
        1. Normalización Canónica.
        2. Cálculo de Merkle Tree.
        3. Cifrado de Sobre (Envelope) del Hash.
        4. Persistencia en WORM Storage.
        5. Registro en DB.
        """
        try:
            # 1. & 2. Normalización y Hashing (Streaming)
            await file.seek(0)
            normalizer = OOXMLNormalizer(file.file)
            canonical_stream = normalizer.get_canonical_stream()
            
            merkle_engine = MerkleEngine()
            # El cálculo consume el stream canónico
            merkle_result = merkle_engine.calculate_root(canonical_stream)
            root_hash = merkle_result["root_hash"]
            
            logger.info(f"Root Hash calculado para sesión {session_id}: {root_hash}")

            # 3. Cifrado de Sobre (Firma del Hash)
            # Ciframos el root_hash usando la llave del tenant para garantizar autenticidad
            envelope = self.crypto_manager.seal_data(root_hash.encode('utf-8'), tenant_id)

            # 4. Persistencia en WORM Storage (S3 Object Lock)
            await file.seek(0) # Resetear puntero para subir el original
            object_key = f"{tenant_id}/{session_id}/{uuid.uuid4()}.docx"
            
            # Subida con Retención Legal
            s3_resp = self.s3.put_object(
                Bucket=self.vault_bucket,
                Key=object_key,
                Body=file.file,
                ObjectLockMode='COMPLIANCE',
                ObjectLockRetention={'Mode': 'COMPLIANCE', 'Days': 1825}, # 5 años
                Metadata={'astra-hash': root_hash}
            )
            
            s3_version_id = s3_resp.get('VersionId', 'null')

            # 5. Registro en Base de Datos
            snapshot = Snapshot(
                tenant_id=tenant_id,
                session_id=session_id,
                artifact_url=f"s3://{self.vault_bucket}/{object_key}",
                s3_version_id=s3_version_id,
                root_hash=root_hash,
                kms_key_id=envelope.key_id,
                encrypted_data_key=envelope.encrypted_dek_b64
            )
            self.db.add(snapshot)
            self.db.commit()
            self.db.refresh(snapshot)
            
            # Guardar estructura del árbol Merkle (si se requiere prueba parcial)
            mt = MerkleTree(
                snapshot_id=snapshot.id,
                tree_structure=merkle_result["tree_structure"]
            )
            self.db.add(mt)
            
            # Log de Auditoría
            self._log_audit(tenant_id, snapshot.id, "SEAL", "SUCCESS", metadata)
            self.db.commit()

            return snapshot

        except Exception as e:
            self.db.rollback()
            logger.error(f"Error en sellado: {e}")
            self._log_audit(tenant_id, None, "SEAL", f"FAILURE: {str(e)}", metadata)
            raise e

    async def verify_integrity(self, snapshot_id: str, file: UploadFile) -> dict:
        """
        Verifica si el archivo subido coincide con el snapshot registrado.
        """
        snapshot = self.db.query(Snapshot).filter(Snapshot.id == snapshot_id).first()
        if not snapshot:
            raise ValueError("Snapshot not found")

        # 1. Recalcular Hash Canónico del archivo entrante
        await file.seek(0)
        normalizer = OOXMLNormalizer(file.file)
        merkle_engine = MerkleEngine()
        current_result = merkle_engine.calculate_root(normalizer.get_canonical_stream())
        current_hash = current_result["root_hash"]

        # 2. Comparar con Hash almacenado (Verdad en DB)
        is_valid_hash = (current_hash == snapshot.root_hash)

        # 3. Registrar auditoría
        audit_status = "VERIFIED" if is_valid_hash else "TAMPERED"
        self._log_audit(snapshot.tenant_id, snapshot.id, "VERIFY", audit_status, {})
        self.db.commit()

        return {
            "is_valid": is_valid_hash,
            "stored_hash": snapshot.root_hash,
            "calculated_hash": current_hash,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _log_audit(self, tenant, snap_id, action, status, meta):
        log = AuditLog(
            tenant_id=tenant,
            snapshot_id=snap_id,
            actor_id="SYSTEM_API", # Debería venir del token
            action=action,
            status=status,
            metadata=meta
        )
        self.db.add(log)
