from typing import Optional
from pydantic_settings import BaseSettings

class StorageSettings(BaseSettings):
    """
    Configuración agnóstica para S3 compatible (AWS S3, Cloudflare R2, MinIO).
    """
    # Endpoint URL: 
    # - R2: https://<account_id>.r2.cloudflarestorage.com
    # - MinIO: http://minio:9000
    STORAGE_ENDPOINT_URL: str
    
    STORAGE_ACCESS_KEY_ID: str
    STORAGE_SECRET_ACCESS_KEY: str
    
    # R2 requiere 'auto', AWS requiere la región real (us-east-1)
    STORAGE_REGION: str = "auto"
    
    # Bucket por defecto
    STORAGE_BUCKET_DEFAULT: str = "astra-data"
    
    # Expiración de URLs prefirmadas en segundos (Default 1 hora)
    STORAGE_PRESIGNED_EXPIRATION: int = 3600

    class Config:
        env_file = ".env"
        extra = "ignore" # Ignorar otras vars
