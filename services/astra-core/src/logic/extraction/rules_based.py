import re
import logging
from typing import List, Dict, Any, Optional
from .base import ExtractionStrategy

logger = logging.getLogger(__name__)

class RulesBasedStrategy(ExtractionStrategy):
    """
    Motor determinista basado en Expresiones Regulares.
    Mapea IDs de plantillas (template_id) a patrones Regex precompilados.
    """

    def __init__(self):
        # Diccionario de patrones por tipo de intención o template_id parcial
        # En producción, esto podría cargarse desde un JSON o DB de configuración
        self.patterns = {
            # Patrón genérico de votación: "Concejal [Nombre] vota [Voto]"
            "VOTACION": re.compile(
                r"(?:el|la)?\s*concejal\s+(?P<CONCEJAL>.+?)\s+(?:vota|dice)\s+(?P<VOTO>s[íi]|no|positivo|negativo|ausente)",
                re.IGNORECASE
            ),
            # Patrón de asistencia: "Concejal [Nombre]: Presente"
            "ASISTENCIA": re.compile(
                r"(?:el|la)?\s*concejal\s+(?P<CONCEJAL>.+?)\s*[:\-\s]\s*(?P<ESTADO>presente|ausente|excusa)",
                re.IGNORECASE
            )
        }

    def _select_pattern(self, schema: List[str], context: Dict) -> Optional[re.Pattern]:
        """
        Selecciona el mejor regex basado en el ID de la plantilla o el esquema.
        """
        template_id = context.get("template_id", "").upper()
        
        # 1. Búsqueda por ID explícito en el nombre de la plantilla
        if "VOTACION" in template_id or "VOTO" in schema:
            return self.patterns["VOTACION"]
        if "LISTA" in template_id or "ASISTENCIA" in template_id or "ESTADO" in schema:
            return self.patterns["ASISTENCIA"]
        
        return None

    async def extract(self, text: str, schema: List[str], context: Optional[Dict] = None) -> List[Dict[str, Any]]:
        if not text or not schema:
            return []

        context = context or {}
        pattern = self._select_pattern(schema, context)

        if not pattern:
            logger.debug(f"RulesStrategy: No se encontró patrón para template {context.get('template_id')}")
            return []

        results = []
        # Finditer para encontrar múltiples ocurrencias (filas) en un mismo bloque de texto
        matches = pattern.finditer(text)
        
        for match in matches:
            row_data = match.groupdict()
            
            # Filtrar solo las llaves que coincidan con el esquema esperado (normalizado)
            # Esto es un mapeo simple, en prod se requiere normalización de keys (upper/lower)
            filtered_row = {}
            for col in schema:
                # Intento simple de match de columnas (CONCEJAL -> CONCEJAL)
                if col in row_data:
                    filtered_row[col] = row_data[col].strip()
                # Fallback mayúsculas
                elif col.upper() in row_data:
                    filtered_row[col] = row_data[col.upper()].strip()

            if filtered_row:
                results.append(filtered_row)

        if results:
            logger.info(f"RulesStrategy: Extraídas {len(results)} filas con éxito.")
        
        return results
