from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "ASTRA-CORE"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    # Transcription Engine (Unified Interface)
    TRANSCRIPTION_PROVIDER: str = "whisper"  # 'whisper', 'parakeet', 'openai'
    WHISPER_MODEL_SIZE: str = "large-v3-turbo"
    WHISPER_DEVICE: str = "cuda"          # 'cuda' o 'cpu'
    WHISPER_COMPUTE_TYPE: str = "float16"  # 'float16', 'int8_float16', 'int8'
    PARAKEET_MODEL: str = "nvidia/parakeet-tdt-0.6b-v2"
    OPENAI_API_KEY: str = ""
    
    # Vector DB & Embeddings
    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "astra_knowledge"
    EMBEDDING_MODEL_PATH: str = "models/paraphrase-multilingual-mpnet-base-v2-quantized.onnx"
    TOKENIZER_PATH: str = "models/tokenizer.json"
    
    # Classification Thresholds
    SIMILARITY_THRESHOLD: float = 0.82    # Mínimo score vectorial para considerar candidato
    EXACT_MATCH_THRESHOLD: float = 95.0   # % Levenshtein para considerar plantilla exacta
    HYBRID_MATCH_THRESHOLD: float = 80.0  # % Levenshtein para considerar híbrido
    
    # QoS & Failover
    S3_ENDPOINT_URL: str = "http://minio:9000"
    S3_FAILOVER_BUCKET: str = "astra-safe-storage"
    AWS_ACCESS_KEY_ID: str = "minioadmin"
    AWS_SECRET_ACCESS_KEY: str = "minioadmin"
    
    # Extraction Settings (New)
    ENABLE_LLM_EXTRACTION: bool = False  # Flag global, puede ser override por request
    LLM_PROVIDER: str = "openai"          # 'openai' | 'groq' | 'local'
    
    # Local LLM Config (Llama-3 + LoRA)
    MODEL_ID: str = "unsloth/llama-3-8b-Instruct-bnb-4bit"
    LORA_ADAPTER_PATH: str = "models/adapters/astra-lora-v1"
    MAX_NEW_TOKENS: int = 1024
    TEMPERATURE: float = 0.3
    
    # Legacy / API Fallback
    LLM_MODEL_NAME: str = "gpt-4o-mini"
    LLM_API_KEY: str = ""

    # Hot-Reload & Caching
    MODEL_CACHE_DIR: str = "models/cache"
    REDIS_EVENT_CHANNEL: str = "astra:events:intelligence"
    MAX_LOADED_ADAPTERS: int = 10  # LRU limit simple

    # Concurrency
    MAX_CONCURRENT_BATCH_JOBS: int = 2
    ENABLE_STREAMING: bool = True
    
    # Limits
    MAX_AUDIO_SIZE_MB: int = 500   # Aumentado para batch de 7h (~1GB)
    AI_TIMEOUT_SECONDS: float = 30.0  # Timeout para hardware económico (L4/T4)

    # RunPod Configuration
    DEEPGRAM_API_KEY: str = "2f1998fcaa0613e03bd2910c5ba57b7cc1fb24c5"
    RUNPOD_API_KEY: str = "rpa_RS6WJ4LHYITSG1XJ36O88LXYW5PY18TX3GOQ6JV9bvav5i"
    RUNPOD_ENDPOINT_INFERENCE: str = ""
    RUNPOD_ENDPOINT_TRAINING: str = ""
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True
    }

@lru_cache
def get_settings():
    return Settings()

settings = get_settings()
