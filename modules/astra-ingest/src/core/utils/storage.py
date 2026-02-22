import os
import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class StorageManager:
    """
    Gestiona la persistencia de archivos. 
    En desarrollo, guarda archivos localmente en _storage/.
    En producción, este punto se extendería para usar boto3 (S3).
    """

    def __init__(self, base_dir: str = "_storage"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(exist_ok=True)

    def upload_bytes(self, data: bytes, s3_uri: str) -> Dict[str, Optional[str]]:
        """
        Simula la subida a S3 persistiendo físicamente en el disco local.
        
        Args:
            data: Contenido binario del archivo.
            s3_uri: URI simulado (ej: s3://bucket/path/file.xml)
            
        Returns:
            Dict: {
                "uri": str, 
                "version_id": str | None
            }
        """
        # 1. Extraer la ruta relativa del URI
        rel_path = s3_uri.replace("s3://", "")
        
        # 2. Construir ruta física
        target_path = self.base_dir / rel_path
        
        # 3. Crear directorios si no existen
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        version_id = None

        # 4. Guardar archivo
        try:
            with open(target_path, "wb") as f:
                f.write(data)
            
            # NOTA PARA IMPLEMENTACIÓN S3/BOTO3:
            # response = s3_client.put_object(Bucket=..., Key=..., Body=data)
            # version_id = response.get('VersionId')
            
            # Simulación local: En un FS real no hay versioning automático, 
            # retornamos None o un placeholder si quisiéramos probar la lógica.
            # version_id = "local-v1" 
            
            logger.debug(f"Archivo persistido localmente: {target_path} (mapeado a {s3_uri})")
        except Exception as e:
            logger.error(f"Error persistiendo archivo en storage local: {e}")
            raise

        return {
            "uri": s3_uri,
            "version_id": version_id
        }

    def get_local_path(self, s3_uri: str) -> Path:
        """Convierte un URI S3 simulado a su ruta física local."""
        rel_path = s3_uri.replace("s3://", "")
        return self.base_dir / rel_path