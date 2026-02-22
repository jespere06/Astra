from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class ExtractionStrategy(ABC):
    """Interfaz para estrategias de extracción de datos estructurados."""

    @abstractmethod
    async def extract(
        self, 
        text: str, 
        schema: List[str], 
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Extrae entidades del texto basándose en un esquema de columnas esperado.
        
        Args:
            text: Texto limpio a procesar.
            schema: Lista de nombres de columnas esperadas (ej: ["CONCEJAL", "VOTO"]).
            context: Metadatos adicionales (tenant_id, template_id, etc).
            
        Returns:
            Lista de filas (diccionarios) con los datos extraídos.
            Retorna lista vacía [] si no se encuentran datos o hay error.
        """
        pass
