import hashlib
import logging
import boto3
from botocore.config import Config
from src.config import settings

logger = logging.getLogger(__name__)

class AudioIntegrityService:
    """
    Gestiona la verificación y sellado de evidencia auditiva en el bucket WORM.
    """
    
    def __init__(self):
        self.s3 = boto3.client(
            's3',
            region_name=settings.AWS_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(signature_version='s3v4', retries={'max_attempts': 3})
        )
        self.vault_bucket = settings.GUARD_AUDIO_VAULT_BUCKET

    def calculate_audio_hash(self, s3_key: str, version_id: str = None) -> str:
        """
        Descarga el audio en streaming y calcula su SHA-256 al vuelo.
        
        Args:
            s3_key: Ruta del objeto en el bucket de audio WORM.
            version_id: ID de versión específico (opcional pero recomendado para inmutabilidad).
            
        Returns:
            Hex string del SHA-256.
        """
        logger.info(f"Calculando hash de audio para {s3_key}...")
        
        sha256_hash = hashlib.sha256()
        
        try:
            # Configurar kwargs
            get_args = {'Bucket': self.vault_bucket, 'Key': s3_key}
            if version_id:
                get_args['VersionId'] = version_id

            # Obtener stream
            response = self.s3.get_object(**get_args)
            stream = response['Body']
            
            # Leer en chunks de 8MB para balancear I/O y CPU
            for chunk in stream.iter_chunks(chunk_size=8 * 1024 * 1024):
                sha256_hash.update(chunk)
                
            final_hash = sha256_hash.hexdigest()
            logger.info(f"Hash calculado: {final_hash[:10]}...")
            return final_hash
            
        except Exception as e:
            logger.error(f"Fallo calculando hash de audio: {e}")
            raise RuntimeError(f"AUDIO_INTEGRITY_FAILURE: {str(e)}")

    def verify_worm_status(self, s3_key: str) -> bool:
        """
        Verifica que el objeto tenga Object Lock habilitado.
        """
        try:
            retention = self.s3.get_object_retention(
                Bucket=self.vault_bucket,
                Key=s3_key
            )
            mode = retention.get('Retention', {}).get('Mode')
            return mode == 'COMPLIANCE'
        except Exception:
            # Si falla (ej. no tiene retención configurada), retornamos False
            # En local (MinIO sin lock) esto podría fallar, manejar según entorno.
            return False
