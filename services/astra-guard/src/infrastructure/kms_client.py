import boto3
import logging
from botocore.config import Config
from src.config import settings
from src.crypto.kms_provider import IKMSProvider, DataKey

logger = logging.getLogger(__name__)

class AWSKMSDriver(IKMSProvider):
    def __init__(self):
        self.client = boto3.client(
            'kms',
            region_name=settings.AWS_REGION,
            endpoint_url=settings.KMS_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            config=Config(retries={'max_attempts': 3, 'mode': 'standard'})
        )

    def generate_data_key(self, key_id: str, key_spec: str = "AES_256") -> DataKey:
        try:
            response = self.client.generate_data_key(
                KeyId=key_id,
                KeySpec=key_spec
            )
            return DataKey(
                plaintext=response['Plaintext'],
                ciphertext=response['CiphertextBlob'],
                key_id=response['KeyId']
            )
        except Exception as e:
            logger.error(f"Error generando Data Key en KMS para {key_id}: {e}")
            raise

    def decrypt_data_key(self, encrypted_key: bytes, key_id: str) -> bytes:
        try:
            response = self.client.decrypt(
                CiphertextBlob=encrypted_key,
                KeyId=key_id # Contexto de encriptación opcional aquí
            )
            return response['Plaintext']
        except Exception as e:
            logger.error(f"Error descifrando Data Key en KMS: {e}")
            raise
