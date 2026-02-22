import logging
import io
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Union, IO, Optional

from .interface import IStorageProvider
from .config import StorageSettings

logger = logging.getLogger(__name__)

class S3StorageAdapter(IStorageProvider):
    def __init__(self, settings: Optional[StorageSettings] = None):
        self.settings = settings or StorageSettings()
        
        # Configuración crítica para Cloudflare R2 y Resiliencia
        self.boto_config = Config(
            signature_version='s3v4',
            retries={
                'max_attempts': 3,
                'mode': 'standard'
            }
        )
        
        self.client = boto3.client(
            's3',
            endpoint_url=self.settings.STORAGE_ENDPOINT_URL,
            aws_access_key_id=self.settings.STORAGE_ACCESS_KEY_ID,
            aws_secret_access_key=self.settings.STORAGE_SECRET_ACCESS_KEY,
            region_name=self.settings.STORAGE_REGION,
            config=self.boto_config
        )

    def _get_bucket(self, bucket: Optional[str]) -> str:
        return bucket or self.settings.STORAGE_BUCKET_DEFAULT

    def upload(self, file_obj: Union[bytes, IO], key: str, bucket: Optional[str] = None, content_type: str = "application/octet-stream") -> str:
        target_bucket = self._get_bucket(bucket)
        
        # Normalizar input a file-like object
        if isinstance(file_obj, bytes):
            data = io.BytesIO(file_obj)
        else:
            data = file_obj
            # Asegurar que estamos al inicio si es un archivo reusado
            if hasattr(data, 'seek'):
                data.seek(0)

        try:
            # upload_fileobj maneja Multipart Upload automáticamente para archivos grandes
            self.client.upload_fileobj(
                data,
                target_bucket,
                key,
                ExtraArgs={'ContentType': content_type}
            )
            return f"s3://{target_bucket}/{key}"
        except ClientError as e:
            logger.error(f"Fallo subiendo archivo a {target_bucket}/{key}: {e}")
            raise

    def download(self, key: str, bucket: Optional[str] = None) -> bytes:
        target_bucket = self._get_bucket(bucket)
        buffer = io.BytesIO()
        try:
            self.client.download_fileobj(target_bucket, key, buffer)
            return buffer.getvalue()
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                raise FileNotFoundError(f"Objeto no encontrado: {key}")
            logger.error(f"Fallo descargando {key}: {e}")
            raise

    def download_to_file(self, key: str, destination_path: str, bucket: Optional[str] = None) -> None:
        target_bucket = self._get_bucket(bucket)
        try:
            self.client.download_file(target_bucket, key, destination_path)
        except ClientError as e:
            logger.error(f"Fallo descargando a archivo {key}: {e}")
            raise

    def generate_presigned_url(self, key: str, operation: str = "get_object", bucket: Optional[str] = None, expiration: int = None) -> str:
        target_bucket = self._get_bucket(bucket)
        expires_in = expiration or self.settings.STORAGE_PRESIGNED_EXPIRATION
        
        try:
            url = self.client.generate_presigned_url(
                ClientMethod=operation,
                Params={'Bucket': target_bucket, 'Key': key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            logger.error(f"Fallo generando URL prefirmada para {key}: {e}")
            raise

    def delete(self, key: str, bucket: Optional[str] = None) -> bool:
        target_bucket = self._get_bucket(bucket)
        try:
            self.client.delete_object(Bucket=target_bucket, Key=key)
            return True
        except ClientError as e:
            logger.error(f"Fallo eliminando {key}: {e}")
            return False

    def exists(self, key: str, bucket: Optional[str] = None) -> bool:
        target_bucket = self._get_bucket(bucket)
        try:
            self.client.head_object(Bucket=target_bucket, Key=key)
            return True
        except ClientError:
            return False
