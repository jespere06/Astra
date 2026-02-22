from pydantic import BaseModel, Field
from typing import Dict, Optional, List

class ProcessingContext(BaseModel):
    """
    Contexto de ejecución que acompaña al audio/texto.
    Contiene la configuración específica del inquilino para este request.
    """
    tenant_id: str
    session_id: Optional[str] = None
    
    # El diccionario clave para el Enricher
    # Ej: {"jhon": "John", "concejal perez": "H.C. Pérez"}
    entities_dictionary: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapa de correcciones determinísticas (Hotfixes) para entidades."
    )
    
    # Otros metadatos necesarios para el flujo
    adapter_id: Optional[str] = "base-model-v1"
    current_speaker_id: Optional[str] = None
