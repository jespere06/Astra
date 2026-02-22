from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://astra:astra_secure_pass@postgres:5432/astra_db"
    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = "admin"
    MINIO_SECRET_KEY: str = "astra_minio_pass"
    MINIO_BUCKET_ASSETS: str = "astra-assets"
    MINIO_BUCKET_SKELETONS: str = "astra-skeletons"
    MINIO_SECURE: bool = False
    QDRANT_URL: str = "http://qdrant:6333"
    ENVIRONMENT: str = "production"

    # RunPod Configuration
    RUNPOD_API_KEY: str = ""
    RUNPOD_ENDPOINT_INFERENCE: str = ""
    RUNPOD_ENDPOINT_TRAINING: str = ""

    # --- [NUEVO] Aligner Heuristics (Fase 3-T01) ---
    # Cuántos segmentos de audio mirar hacia adelante para agrupar
    ALIGNER_MAX_LOOKAHEAD: int = 40
    # Umbral mínimo de similitud coseno para aceptar un par
    ALIGNER_SIMILARITY_THRESHOLD: float = 0.35 #0.45
    # Factor de penalización por diferencia de longitud (0.0 = desactivado, 0.2 = recomendado)
    # Penaliza si el audio es mucho más largo que el texto XML
    ALIGNER_LENGTH_PENALTY: float = 0.0 #0.05
    # Tolerancia en segundos para "viajar en el tiempo" hacia atrás
    # Permite que un resumen asocie audio que ocurrió levemente antes del último punto.
    ALIGNER_TIME_TOLERANCE_SEC: float = 15.0

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()