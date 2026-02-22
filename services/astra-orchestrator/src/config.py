from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "ASTRA Orchestrator"
    REDIS_URL: str = "redis://redis:6379/0"
    GRPC_PORT: int = 50055  # Nuevo puerto para gRPC
    
    TENANT_CONFIG_URL: str = "http://tenant-config-service:8080"
    CORE_URL: str = "http://astra-core:8001/v1/core"
    
    # S3 / MinIO Settings
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    AWS_REGION: str = "us-east-1"
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_BUCKET_NAME: str = "astra-audio-fallback"
    
    # VAD & Ingesta (Fase 3-T03)
    VAD_ENERGY_THRESHOLD: int = 300
    AI_TIMEOUT_SECONDS: float = 4.0
    MAX_TEXT_LENGTH: int = 10000
    S3_FAILOVER_BUCKET: str = "astra-failover-audio"
    
    # Finalization & Handover
    BUILDER_URL: str = "http://astra-builder:8080"
    HANDOVER_THRESHOLD_BYTES: int = 5 * 1024 * 1024 # 5 MB
    S3_HANDOVER_BUCKET: str = "astra-session-handover"
    
    # Asset Management (Fase 3-T04)
    INGEST_GRPC_URL: str = "astra-ingest:50051"
    INGEST_SERVICE_URL: str = "http://localhost:8003"
    S3_BUCKET_ASSETS: str = "astra-assets"
    
    # ASTRA-GUARD Integration
    ASTRA_GUARD_URL: str = "http://astra-guard:8003"
    ASTRA_INTERNAL_SERVICE_KEY: str = "astra_service_key_v1"

    MAX_IMAGE_WIDTH: int = 1920
    IMAGE_QUALITY: int = 80
    ALLOWED_IMAGE_TYPES: list = ["image/jpeg", "image/png", "image/webp"]

    # Batch Jobs / RunPod Serverless
    RUNPOD_API_KEY: str = "rpa_RS6WJ4LHYITSG1XJ36O88LXYW5PY18TX3GOQ6JV9bvav5i"
    RUNPOD_ENDPOINT_ID: str = ""
    RUNPOD_BASE_URL: str = "https://api.runpod.ai"
    S3_BATCH_BUCKET: str = "astra-batch-audio"
    WEBHOOK_SECRET: str = ""
    WEBHOOK_CALLBACK_BASE_URL: str = "http://localhost:8000"  # Public URL del orchestrator
    JOB_TTL_SECONDS: int = 604800    # 7 días
    JOB_MAX_RETRIES: int = 2

    ENVIRONMENT: str = "development"
    SESSION_TTL_SECONDS: int = 86400  # 24 Horas

    # Security / JWT
    JWT_SECRET_KEY: str = "dev_secret_key_change_in_prod"
    JWT_ALGORITHM: str = "HS256"

    class Config:
        env_file = ".env"

settings = Settings()
