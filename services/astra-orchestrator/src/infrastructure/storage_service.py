import boto3
import logging
from botocore.config import Config
from src.config import settings

logger = logging.getLogger(__name__)

class StorageService:
    def __init__(self):
        # Configurar boto3 con endpoint personalizado para MinIO
        self.s3 = boto3.client(
            's3',
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
            config=Config(signature_version='s3v4')
        )
        # Asegurar buckets críticos
        self._ensure_bucket(settings.S3_FAILOVER_BUCKET)
        self._ensure_bucket(settings.S3_HANDOVER_BUCKET)

    def _ensure_bucket(self, bucket_name: str):
        try:
            self.s3.head_bucket(Bucket=bucket_name)
        except Exception:
            logger.info(f"Creating bucket: {bucket_name}")
            try:
                self.s3.create_bucket(Bucket=bucket_name)
            except Exception as e:
                logger.error(f"Failed to create bucket {bucket_name}: {e}")

    async def upload_failover_audio(self, session_id: str, sequence_id: int, content: bytes) -> str:
        """Sube audio a S3 y genera URL presignada de 7 días"""
        key = f"failover/{session_id}/{sequence_id}.wav"
        
        try:
            # Sincrónico (boto3), aceptable para MVP. En alta carga usar run_in_executor
            self.s3.put_object(
                Bucket=settings.S3_FAILOVER_BUCKET,
                Key=key,
                Body=content
            )

            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.S3_FAILOVER_BUCKET, 'Key': key},
                ExpiresIn=604800 
            )
            return url
        except Exception as e:
            logger.error(f"Failed to upload failover audio to S3: {e}")
            return ""

    async def upload_session_dump(self, session_id: str, json_content: str) -> str:
        """Sube JSON Dump completo y retorna URL Presignada (Handover)"""
        key = f"dumps/{session_id}/session_dump.json"
        
        try:
            self.s3.put_object(
                Bucket=settings.S3_HANDOVER_BUCKET,
                Key=key,
                Body=json_content,
                ContentType='application/json'
            )
            
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': settings.S3_HANDOVER_BUCKET, 'Key': key},
                ExpiresIn=3600
            )
            return url
        except Exception as e:
            logger.error(f"Failed to upload session dump: {e}")
            raise

    async def upload_generic_file(self, bucket: str, key: str, data: bytes) -> str:
        """Sube cualquier archivo a S3"""
        try:
            self.s3.put_object(Bucket=bucket, Key=key, Body=data)
            return f"{settings.S3_ENDPOINT_URL}/{bucket}/{key}"
        except Exception as e:
            logger.error(f"Failed generic upload: {e}")
            raise

    async def delete_prefix(self, bucket: str, prefix: str):
        """
        Elimina todos los objetos bajo un prefijo específico.
        Usado para limpieza de sesión.
        """
        try:
            # 1. Listar objetos
            response = self.s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            
            if 'Contents' not in response:
                return

            # 2. Preparar batch de borrado
            objects_to_delete = [{'Key': obj['Key']} for obj in response['Contents']]
            
            if objects_to_delete:
                self.s3.delete_objects(
                    Bucket=bucket,
                    Delete={'Objects': objects_to_delete}
                )
                logger.info(f"🧹 Limpiados {len(objects_to_delete)} objetos de {bucket}/{prefix}")

        except Exception as e:
            logger.error(f"Error cleaning up S3 prefix {bucket}/{prefix}: {e}")
