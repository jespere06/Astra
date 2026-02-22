from pydantic_settings import BaseSettings
import os

class Settings(BaseSettings):
    # K8s Config
    K8S_NAMESPACE: str = "astra-mlops"
    TRAINER_IMAGE: str = "astra/astra-trainer:v1.0.0"
    
    # MLflow
    MLFLOW_URI: str = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    
    # Training Thresholds
    BATCH_SIZE_THRESHOLD: int = 500
    MAX_WAIT_HOURS: int = 168  # 1 week
    
    # Model Config
    BASE_MODEL_ID: str = "meta-llama/Llama-2-7b-hf"

    # RunPod Serverless Config
    RUNPOD_API_KEY: str = "rpa_RS6WJ4LHYITSG1XJ36O88LXYW5PY18TX3GOQ6JV9bvav5i"
    RUNPOD_ENDPOINT_ID: str = ""
    
    # Configuración de Cliente HTTP
    HTTP_TIMEOUT_CONNECT: float = 10.0
    HTTP_TIMEOUT_READ: float = 30.0
    
    # [Fase2-T07] Backend Selector
    TRAINING_BACKEND: str = "K8S" # Values: 'K8S', 'RUNPOD'
    
    # S3 Config for Presigning (Needed for RunPod)
    S3_BUCKET_NAME: str = "astra-models"

    class Config:
        env_file = ".env"
        extra = "ignore" # Permitir variables extra en .env

settings = Settings()
