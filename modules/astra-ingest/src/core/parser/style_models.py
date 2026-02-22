from dataclasses import dataclass
from typing import Optional

@dataclass
class StyleDefinition:
    """Representación intermedia de un estilo extraído del XML."""
    style_id: str
    name: str
    type: str  # 'paragraph', 'character', 'table', etc.
    is_default: bool = False
    
    # Propiedades para inferencia
    outline_level: Optional[int] = None  # w:outlineLvl
    font_size: Optional[int] = None      # w:sz (en medios puntos)
    is_bold: bool = False                # w:b
    is_italic: bool = False              # w:i