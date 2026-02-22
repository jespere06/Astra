"""
Configuración del Worker via variables de entorno.
Inyectadas por RunPod, Modal, o docker-compose.
"""
from pydantic_settings import BaseSettings


class WorkerSettings(BaseSettings):
    # ── Job Identity ──
    JOB_ID: str = ""
    TENANT_ID: str = ""

    # ── Input/Output ──
    INPUT_AUDIO_URL: str = ""           # Presigned URL o s3://bucket/key
    OUTPUT_S3_BUCKET: str = "astra-transcripts"
    OUTPUT_S3_KEY: str = ""             # Se auto-genera si vacío

    # ── Transcription Engine ──
    TRANSCRIPTION_PROVIDER: str = "whisper"   # whisper | parakeet | openai
    WHISPER_MODEL_SIZE: str = "large-v3-turbo"
    WHISPER_DEVICE: str = "cuda"
    WHISPER_COMPUTE_TYPE: str = "float16"
    PARAKEET_MODEL: str = "nvidia/parakeet-tdt-0.6b-v2"
    OPENAI_API_KEY: str = ""

    # ── S3 / R2 Storage ──
    S3_ENDPOINT_URL: str = ""           # Vacío = AWS nativo. Para R2: https://<id>.r2.cloudflarestorage.com
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_DEFAULT_REGION: str = "us-east-1"

    # ── Callback ──
    WEBHOOK_URL: str = ""               # POST aquí al terminar
    WEBHOOK_SECRET: str = ""            # HMAC signing key

    # ── Runtime ──
    TEMP_DIR: str = "/app/tmp"
    LOG_LEVEL: str = "INFO"

    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


settings = WorkerSettings()
