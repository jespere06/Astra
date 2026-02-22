from abc import ABC, abstractmethod
from typing import IO, Optional, Union

class IStorageProvider(ABC):
    """Interfaz abstracta para operaciones de almacenamiento de objetos."""

    @abstractmethod
    def upload(self, file_obj: Union[bytes, IO], key: str, bucket: Optional[str] = None, content_type: str = "application/octet-stream") -> str:
        """Sube un objeto y retorna su URI interna (s3://...)."""
        pass

    @abstractmethod
    def download(self, key: str, bucket: Optional[str] = None) -> bytes:
        """Descarga el contenido de un objeto a memoria."""
        pass
    
    @abstractmethod
    def download_to_file(self, key: str, destination_path: str, bucket: Optional[str] = None) -> None:
        """Descarga un objeto directamente a un archivo local."""
        pass

    @abstractmethod
    def generate_presigned_url(self, key: str, operation: str = "get_object", bucket: Optional[str] = None, expiration: int = 3600) -> str:
        """Genera una URL temporal de acceso público."""
        pass

    @abstractmethod
    def delete(self, key: str, bucket: Optional[str] = None) -> bool:
        """Elimina un objeto."""
        pass
    
    @abstractmethod
    def exists(self, key: str, bucket: Optional[str] = None) -> bool:
        """Verifica si un objeto existe."""
        pass
