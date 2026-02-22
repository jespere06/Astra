import os
import logging
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from src.config import settings
from src.crypto.kms_provider import IKMSProvider
from dataclasses import dataclass
import base64
from typing import Dict, Any

logger = logging.getLogger(__name__)

@dataclass
class SealedEnvelope:
    """El paquete final que se guarda en la base de datos."""
    key_id: str             # ARN de la CMK del Tenant
    encrypted_dek_b64: str  # DEK cifrada (base64)
    ciphertext_b64: str     # Hash/Datos cifrados (base64)
    iv_b64: str             # Vector de Inicialización (base64)
    tag_b64: str            # Tag de autenticación GCM (base64)

class EncryptionManager:
    def __init__(self, provider: IKMSProvider):
        self.provider = provider
        self.settings = settings

    def _get_cmk_for_tenant(self, tenant_id: str) -> str:
        """Resuelve el ARN de la llave maestra para un inquilino."""
        key_arn = self.settings.get_tenant_key_arn(tenant_id)
        if not key_arn:
            logger.error(f"Intento de cifrado para tenant no configurado: {tenant_id}")
            raise ValueError(f"No KMS configuration found for tenant: {tenant_id}")
        return key_arn

    def seal_data(self, data: bytes, tenant_id: str) -> SealedEnvelope:
        """
        Aplica Envelope Encryption:
        1. Pide DEK al KMS (usando la CMK del tenant).
        2. Cifra los datos locales con la DEK (AES-256-GCM).
        3. Borra la DEK de memoria.
        4. Retorna el sobre.
        """
        # 1. Obtener CMK y DEK
        cmk_arn = self._get_cmk_for_tenant(tenant_id)
        data_key = self.provider.generate_data_key(cmk_arn)

        try:
            # 2. Cifrado Local (AES-GCM)
            iv = os.urandom(12) # GCM recomienda 12 bytes
            cipher = Cipher(
                algorithms.AES(data_key.plaintext),
                modes.GCM(iv),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            ciphertext = encryptor.update(data) + encryptor.finalize()
            
            return SealedEnvelope(
                key_id=cmk_arn,
                encrypted_dek_b64=base64.b64encode(data_key.ciphertext).decode('utf-8'),
                ciphertext_b64=base64.b64encode(ciphertext).decode('utf-8'),
                iv_b64=base64.b64encode(iv).decode('utf-8'),
                tag_b64=base64.b64encode(encryptor.tag).decode('utf-8')
            )
        finally:
            # 3. Limpieza proactiva (Best effort en Python)
            if hasattr(data_key, 'plaintext'):
                # Intentar sobreescribir si fuera mutable, pero bytes no lo es. 
                # Solo podemos eliminar la referencia.
                data_key.plaintext = b"" 
                del data_key.plaintext
    
    def unseal_data(self, envelope: SealedEnvelope) -> bytes:
        """
        Abre el sobre:
        1. Pide al KMS descifrar la DEK.
        2. Usa la DEK para descifrar los datos locales.
        """
        # 1. Descifrar DEK
        encrypted_dek = base64.b64decode(envelope.encrypted_dek_b64)
        plaintext_dek = self.provider.decrypt_data_key(encrypted_dek, envelope.key_id)
        
        try:
            # 2. Descifrar Datos
            iv = base64.b64decode(envelope.iv_b64)
            ciphertext = base64.b64decode(envelope.ciphertext_b64)
            tag = base64.b64decode(envelope.tag_b64)
            
            cipher = Cipher(
                algorithms.AES(plaintext_dek),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            
            return decryptor.update(ciphertext) + decryptor.finalize()
        finally:
            del plaintext_dek
