import boto3
import logging
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Generator, Tuple
from src.config import settings

logger = logging.getLogger(__name__)

class StorageGateway:
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            region_name=settings.AWS_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4')
        )

    def verify_object_integrity(self, s3_uri: str, expected_version_id: str) -> bool:
        """
        [GRD-05.2] Idempotencia: Verifica que el objeto exista y coincida con la versión sellada.
        Realiza un HEAD object para validar metadata sin descargar contenido.
        """
        bucket, key = self._parse_uri(s3_uri)
        try:
            # Validamos que la versión específica siga existiendo y no haya sido borrada (delete marker)
            response = self.s3.head_object(
                Bucket=bucket, 
                Key=key,
                VersionId=expected_version_id
            )
            # Verificaciones extra de WORM si es necesario (ObjectLockMode)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] in ("404", "NoSuchKey", "NoSuchVersion"):
                logger.critical(f"ALERTA DE INTEGRIDAD: El objeto sellado {s3_uri} (v: {expected_version_id}) no se encuentra.")
                return False
            raise e

    def get_object_stream(self, s3_uri: str, version_id: str) -> Generator[bytes, None, None]:
        """Retorna un generador de bytes para streaming eficiente."""
        bucket, key = self._parse_uri(s3_uri)
        try:
            response = self.s3.get_object(
                Bucket=bucket, 
                Key=key, 
                VersionId=version_id
            )
            # Stream de chunks de 64KB
            for chunk in response['Body'].iter_chunks(chunk_size=65536):
                yield chunk
        except Exception as e:
            logger.error(f"Error descargando objeto {s3_uri}: {e}")
            raise e

    def _parse_uri(self, uri: str) -> Tuple[str, str]:
        # s3://bucket/key
        parts = uri.replace("s3://", "").split("/", 1)
        return parts[0], parts[1]
