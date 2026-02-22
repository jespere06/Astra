import hmac
import hashlib
from src.config import settings

class DigitalSealer:
    """
    Simula un HSM o KMS. Genera una firma HMAC basada en el contenido
    y una llave maestra del sistema.
    """
    
    @staticmethod
    def sign_manifest(integrity_hash: str, tenant_id: str, session_id: str) -> str:
        # La "firma" vincula el hash del archivo con el contexto (tenant/session)
        # para evitar que un hash válido sea reutilizado en otro contexto.
        payload = f"{integrity_hash}|{tenant_id}|{session_id}"
        
        signature = hmac.new(
            key=settings.SYSTEM_SECRET_KEY.encode(),
            msg=payload.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()
        
        return signature

    @staticmethod
    def verify_signature(signature: str, integrity_hash: str, tenant_id: str, session_id: str) -> bool:
        expected = DigitalSealer.sign_manifest(integrity_hash, tenant_id, session_id)
        return hmac.compare_digest(signature, expected)
