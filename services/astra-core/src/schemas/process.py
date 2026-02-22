from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.generated.astra_models_pb2 import IntentType # Asumiendo DTO generado

class ProcessingRequest(BaseModel):
    tenant_id: str = Field(..., min_length=3)
    client_timezone: str = Field(default="UTC")
    entities_dictionary: Dict[str, str] = Field(default_factory=dict)
    
    # Payload (uno de los dos debe estar presente)
    audio_content: Optional[bytes] = None
    audio_filename: Optional[str] = "audio.wav"
    text_content: Optional[str] = None
    
    # Config
    flags: Dict[str, bool] = Field(default_factory=lambda: {"prefer_formal": True})

    @field_validator('client_timezone')
    @classmethod
    def validate_timezone(cls, v):
        try:
            ZoneInfo(v)
            return v
        except ZoneInfoNotFoundError:
            return "UTC"

class AstraBlockResponse(BaseModel):
    raw_text: str
    clean_text: str
    intent: Any # Enum Value or Int
    template_id: str
    confidence: float
    structured_data: Optional[List[Any]] = None
    metadata: Dict[str, Any]
    
    # Trazabilidad
    processed_at: str
    processing_time_ms: float
    warnings: List[str] = []
