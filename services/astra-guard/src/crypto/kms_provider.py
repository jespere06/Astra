from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple

@dataclass
class DataKey:
    """Representa una llave de datos (DEK) generada por el KMS."""
    plaintext: bytes  # La llave cruda para usar en memoria (NO PERSISTIR)
    ciphertext: bytes # La llave cifrada por la CMK (SÍ PERSISTIR)
    key_id: str       # ARN de la CMK que la generó

class IKMSProvider(ABC):
    """Interfaz abstracta para operaciones de KMS."""

    @abstractmethod
    def generate_data_key(self, key_id: str, key_spec: str = "AES_256") -> DataKey:
        """
        Solicita al KMS una nueva llave de datos (DEK).
        """
        pass

    @abstractmethod
    def decrypt_data_key(self, encrypted_key: bytes, key_id: str) -> bytes:
        """
        Solicita al KMS descifrar una DEK para usarla.
        """
        pass
