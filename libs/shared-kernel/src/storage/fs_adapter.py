import os
import shutil
import logging
from typing import Union, IO, Optional
from .interface import IStorageProvider

logger = logging.getLogger(__name__)

class FileSystemStorageAdapter(IStorageProvider):
    """
    Implementación de almacenamiento en sistema de archivos local.
    Útil para entornos On-Premise sin Object Storage o para desarrollo.
    """
    def __init__(self, root_path: str = "/data/storage", base_url: str = "http://localhost/files"):
        self.root_path = root_path
        self.base_url = base_url.rstrip("/")
        os.makedirs(self.root_path, exist_ok=True)

    def _get_abs_path(self, key: str, bucket: str) -> str:
        # Sanitización básica para evitar Path Traversal
        safe_key = key.lstrip("/")
        safe_bucket = bucket or "default"
        return os.path.join(self.root_path, safe_bucket, safe_key)

    def upload(self, file_obj: Union[bytes, IO], key: str, bucket: Optional[str] = None, content_type: str = "application/octet-stream") -> str:
        target_path = self._get_abs_path(key, bucket)
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        try:
            if isinstance(file_obj, bytes):
                with open(target_path, "wb") as f:
                    f.write(file_obj)
            else:
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                with open(target_path, "wb") as dst:
                    shutil.copyfileobj(file_obj, dst)
            
            logger.info(f"Archivo guardado localmente en: {target_path}")
            # Retorna una URI file:// interna
            return f"file://{target_path}"
        except Exception as e:
            logger.error(f"Error escribiendo en disco: {e}")
            raise

    def download(self, key: str, bucket: Optional[str] = None) -> bytes:
        target_path = self._get_abs_path(key, bucket)
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Archivo no encontrado: {target_path}")
        
        with open(target_path, "rb") as f:
            return f.read()

    def download_to_file(self, key: str, destination_path: str, bucket: Optional[str] = None) -> None:
        target_path = self._get_abs_path(key, bucket)
        if not os.path.exists(target_path):
            raise FileNotFoundError(f"Archivo no encontrado: {target_path}")
        shutil.copy2(target_path, destination_path)

    def generate_presigned_url(self, key: str, operation: str = "get_object", bucket: Optional[str] = None, expiration: int = 3600) -> str:
        # En FS local no hay presigned URLs reales.
        # Retornamos una URL simulada que debería ser servida por un servidor de estáticos.
        safe_bucket = bucket or "default"
        return f"{self.base_url}/{safe_bucket}/{key}"

    def delete(self, key: str, bucket: Optional[str] = None) -> bool:
        target_path = self._get_abs_path(key, bucket)
        try:
            if os.path.exists(target_path):
                os.remove(target_path)
                return True
            return False
        except Exception as e:
            logger.error(f"Error eliminando archivo {target_path}: {e}")
            return False

    def exists(self, key: str, bucket: Optional[str] = None) -> bool:
        target_path = self._get_abs_path(key, bucket)
        return os.path.exists(target_path)
