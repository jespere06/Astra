from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Dict, Optional, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

class SessionStartRequest(BaseModel):
    tenant_id: str = Field(..., min_length=3, description="Identificador único del cliente/organismo")
    skeleton_id: str = Field(..., min_length=1, description="ID de la plantilla base en S3")
    client_timezone: str = Field(default="America/Bogota", description="Zona horaria para timestamps locales")
    metadata: Optional[Dict[str, Any]] = Field(
        default={}, 
        description="Datos adicionales libres (ej. nombre_acta, fecha, participantes)"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "tenant_id": "concejo-bogota",
                "skeleton_id": "plantilla-plenaria-v2",
                "client_timezone": "America/Bogota",
                "metadata": {
                    "tipo_sesion": "Ordinaria",
                    "numero_acta": "045-2024",
                    "secretario": "Juan Perez"
                }
            }
        }
    )

    @field_validator('client_timezone')
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        try:
            ZoneInfo(v)
            return v
        except ZoneInfoNotFoundError:
            raise ValueError(f"Timezone '{v}' no es una zona IANA válida.")

class SessionContextUpdate(BaseModel):
    """Payload para el PATCH de contexto dinámico"""
    current_speaker_id: Optional[str] = Field(None, description="ID del orador actual")
    topic: Optional[str] = Field(None, description="Tema en discusión")
    is_restricted: Optional[bool] = Field(None, description="Flag de privacidad/reserva legal")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_speaker_id": "concejal-lopez",
                "topic": "Debate Control Político",
                "is_restricted": False
            }
        }
    )

class CurrentContextResponse(BaseModel):
    """Estado actual del contexto en la sesión"""
    current_speaker_id: str
    topic: str
    is_restricted: bool

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "current_speaker_id": "concejal-lopez",
                "topic": "Debate Control Político",
                "is_restricted": False
            }
        }
    )

class PinnedConfig(BaseModel):
    """Configuración inmutable capturada al inicio de la sesión"""
    s3_version_id: str
    adapter_id: str
    style_map: Dict[str, str]
    zone_map: Dict[str, str]
    table_map: Dict[str, str]

class SessionState(BaseModel):
    session_id: str
    tenant_id: str
    status: str
    skeleton_id: str
    pinned_config: PinnedConfig
    client_timezone: str
    created_at: str
