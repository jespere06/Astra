from pydantic import BaseModel, field_validator
from typing import List, Optional
from uuid import UUID
from src.core.mapping.constants import VALID_ZONES

class UnmappedTemplateDTO(BaseModel):
    template_id: UUID
    structure_hash: str
    preview_text: Optional[str]
    variables: List[str]
    occurrences_count: int = 0 # Opcional: para mostrar frecuencia

class MappingRequest(BaseModel):
    template_id: UUID
    zone_id: str

    @field_validator('zone_id')
    def validate_zone(cls, v):
        if v not in VALID_ZONES:
            raise ValueError(f"Zona inválida. Debe ser una de: {VALID_ZONES}")
        return v

class BatchMappingRequest(BaseModel):
    mappings: List[MappingRequest]