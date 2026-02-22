from enum import Enum

class DeploymentProfile(str, Enum):
    CLOUD = "CLOUD"      # Acceso total a internet, servicios gestionados (S3, Deepgram)
    ONPREM = "ONPREM"    # Air-gapped o recursos locales (MinIO local, Whisper local)

class TranscriptionProvider(str, Enum):
    DEEPGRAM = "deepgram"
    WHISPER_LOCAL = "whisper_local"
    OPENAI = "openai"
    MOCK = "mock"

class StorageBackend(str, Enum):
    S3 = "s3"            # AWS S3, Cloudflare R2, MinIO
    FILESYSTEM = "filesystem" # Disco local (volumen montado)

class TrainingBackend(str, Enum):
    K8S = "k8s"
    RUNPOD = "runpod"
    LOCAL_DOCKER = "local_docker"
