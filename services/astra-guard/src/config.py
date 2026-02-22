from pydantic_settings import BaseSettings
from typing import Dict

class Settings(BaseSettings):
    # AWS / LocalStack Configuration
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: str = "test"
    AWS_SECRET_ACCESS_KEY: str = "test"
    KMS_ENDPOINT_URL: str = "http://localstack:4566" # Para desarrollo local
    S3_ENDPOINT_URL: str = "http://minio:9000"       # Para MinIO local
    GUARD_VAULT_BUCKET: str = "astra-guard-vault"   # Coincidente con setup-guard en docker-compose
    GUARD_AUDIO_VAULT_BUCKET: str = "astra-audio-vault"
    SYSTEM_SECRET_KEY: str = "astra_internal_secret_change_me"

    # Security Configuration
    JWT_SECRET_KEY: str = "guard_secret_key_change_me"
    JWT_ALGORITHM: str = "HS256"

    KMS_TENANT_MAP_JSON: str = '{"default": "arn:aws:kms:us-east-1:000000000000:key/default-key"}'

    def get_tenant_key_arn(self, tenant_id: str) -> str:
        import json
        try:
            key_map = json.loads(self.KMS_TENANT_MAP_JSON)
            return key_map.get(tenant_id)
        except json.JSONDecodeError:
            return None

    class Config:
        env_file = ".env"

settings = Settings()
