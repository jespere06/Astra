import re
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class TableParser:
    """
    Motor de extracción de datos estructurados para intenciones tipo tabla.
    Intenta mapear variables de la plantilla (ej: {CONCEJAL}) con el texto real.
    """

    @staticmethod
    def extract(template_pattern: str, input_text: str, variables: list) -> Dict[str, Any]:
        """
        Extrae datos estructurados usando heurística de posición o regex dinámico.
        
        Args:
            template_pattern: Texto base de la plantilla (ej: "El concejal {VAR_0} vota {VAR_1}")
            input_text: Texto transcrito (ej: "El concejal Juan Perez vota positivo")
            variables: Lista de nombres de variables en orden (["CONCEJAL", "VOTO"])
        
        Returns:
            Dict con los valores extraídos (ej: {"CONCEJAL": "Juan Perez", "VOTO": "positivo"})
        """
        if not template_pattern or not variables:
            return {}

        # 1. Construir Regex dinámico desde el patrón de la plantilla
        # Escapamos caracteres especiales y reemplazamos los placeholders {VAR_X} por capturas (.*?)
        # Nota: Asumimos que los placeholders en template_pattern son como {VAR_0}, {VAR_1}, etc.
        # En producción esto vendría del campo 'preview_text' o similar de INGEST.
        
        regex_pattern = re.escape(template_pattern)
        
        # Reemplazar marcadores de variables por grupos de captura no codiciosos
        # Ajustar patrón para capturar {VAR_...} o {{VAR_...}} según formato de INGEST
        regex_pattern = re.sub(r'\\\{.*?\\\}', r'(.*?)', regex_pattern)
        
        # Permitir flexibilidad en espacios y puntuación
        regex_pattern = regex_pattern.replace(r'\ ', r'\s+')
        
        try:
            match = re.search(regex_pattern, input_text, re.IGNORECASE)
            if match:
                extracted_data = {}
                groups = match.groups()
                
                # Mapear grupos capturados a nombres de variables
                for i, var_name in enumerate(variables):
                    if i < len(groups):
                        extracted_data[var_name] = groups[i].strip()
                
                return extracted_data
        except Exception as e:
            logger.warning(f"Fallo en extracción regex para tabla: {e}")

        # Fallback: Si falla el regex estricto, retornamos vacío (Builder usará raw text si aplica)
        return {}
