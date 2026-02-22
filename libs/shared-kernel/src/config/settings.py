from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, model_validator
from .enums import DeploymentProfile, TranscriptionProvider, StorageBackend, TrainingBackend

class AstraGlobalSettings(BaseSettings):
    """
    Configuración centralizada para ASTRA.
    Define el comportamiento de la infraestructura según el entorno.
    """
    # Perfil de Despliegue
    ASTRA_PROFILE: DeploymentProfile = Field(default=DeploymentProfile.CLOUD, env="ASTRA_PROFILE")
    
    # Selectores de Implementación
    TRANSCRIPTION_PROVIDER: TranscriptionProvider = Field(default=TranscriptionProvider.WHISPER_LOCAL, env="TRANSCRIPTION_PROVIDER")
    STORAGE_TYPE: StorageBackend = Field(default=StorageBackend.S3, env="STORAGE_TYPE")
    TRAINING_BACKEND: TrainingBackend = Field(default=TrainingBackend.K8S, env="TRAINING_BACKEND")

    # Storage Config
    STORAGE_LOCAL_ROOT: str = Field(default="/data/storage", env="STORAGE_LOCAL_ROOT")
    
    # Cloud Credentials (Opcionales si estamos en ONPREM)
    AWS_ACCESS_KEY_ID: Optional[str] = Field(None, env="AWS_ACCESS_KEY_ID")
    DEEPGRAM_API_KEY: Optional[str] = Field(None, env="DEEPGRAM_API_KEY")
    RUNPOD_API_KEY: Optional[str] = Field(None, env="RUNPOD_API_KEY")

    @model_validator(mode='after')
    def validate_profile_consistency(self):
        """
        Asegura que la configuración sea coherente con el perfil de despliegue.
        """
        profile = self.ASTRA_PROFILE
        
        # Reglas para modo ON-PREM (Seguridad estricta)
        if profile == DeploymentProfile.ONPREM:
            if self.TRANSCRIPTION_PROVIDER in [TranscriptionProvider.DEEPGRAM, TranscriptionProvider.OPENAI]:
                raise ValueError(
                    f"Configuración inválida: No se puede usar {self.TRANSCRIPTION_PROVIDER} en modo {profile}. "
                    "Use 'whisper_local' o configure el perfil como 'CLOUD'."
                )
            
            if self.TRAINING_BACKEND == TrainingBackend.RUNPOD:
                raise ValueError(
                    f"Configuración inválida: No se puede usar RunPod (Nube) en modo {profile}."
                )

        # Reglas para proveedores de Nube (Requerimiento de Credenciales)
        if self.TRANSCRIPTION_PROVIDER == TranscriptionProvider.DEEPGRAM and not self.DEEPGRAM_API_KEY:
            raise ValueError("DEEPGRAM_API_KEY es requerida cuando el proveedor es 'deepgram'.")
            
        if self.TRAINING_BACKEND == TrainingBackend.RUNPOD and not self.RUNPOD_API_KEY:
            raise ValueError("RUNPOD_API_KEY es requerida cuando el backend de entrenamiento es 'runpod'.")

        return self

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

# Instancia singleton para uso en la aplicación
global_settings = AstraGlobalSettings()
