import pytest
from unittest.mock import MagicMock
from src.infrastructure.kms_client import AWSKMSDriver
from src.crypto.manager import EncryptionManager
from src.config import settings

# Estos tests asumen que el driver está configurado para hablar con un KMS
# En un entorno CI real se usaría LocalStack. Aquí probamos la lógica de Envelope.

class TestKMSLogic:
    
    @pytest.fixture
    def manager(self):
        # Mock del driver para no depender de LocalStack en unit tests
        driver = MagicMock(spec=AWSKMSDriver)
        
        # Simular generación de llave de datos
        from src.crypto.kms_provider import DataKey
        mock_dek = DataKey(
            plaintext=b"\x00" * 32,
            ciphertext=b"encrypted_key_blob",
            key_id="arn:aws:kms:key/123"
        )
        driver.generate_data_key.return_value = mock_dek
        driver.decrypt_data_key.return_value = b"\x00" * 32
        
        # Mock de settings para que devuelva una llave válida
        settings.get_tenant_key_arn = MagicMock(return_value="arn:aws:kms:key/tenant-a")
        
        return EncryptionManager(driver)

    def test_seal_unseal_roundtrip(self, manager):
        original_hash = b"5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
        tenant = "tenant-a"
        
        # 1. Sellar (Seal)
        envelope = manager.seal_data(original_hash, tenant)
        
        assert envelope.key_id == "arn:aws:kms:key/tenant-a"
        assert envelope.ciphertext_b64 != original_hash.decode()

        # 2. Abrir (Unseal)
        recovered_data = manager.unseal_data(envelope)
        
        assert recovered_data == original_hash
