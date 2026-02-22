import re
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class EntityEnricher:
    """
    Motor de corrección determinística de entidades (Hotfix Layer).
    Aplica reemplazos basados en un diccionario específico del inquilino,
    respetando límites de palabra y capitalización definida.
    """

    def apply(self, text: str, mapping: Dict[str, str]) -> str:
        """
        Aplica los reemplazos definidos en el mapping sobre el texto.

        Args:
            text: Texto normalizado proveniente del pipeline.
            mapping: Diccionario { 'error_o_alias': 'Forma Correcta' }.

        Returns:
            Texto enriquecido.
        """
        if not text or not mapping:
            return text

        try:
            # 1. Preparación del Diccionario
            # Normalizamos las llaves a minúsculas para búsqueda insensible a mayúsculas.
            # Los valores se mantienen intactos (es la forma correcta que queremos inyectar).
            lookup_map = {k.lower().strip(): v.strip() for k, v in mapping.items() if k and v}

            if not lookup_map:
                return text

            # 2. Ordenamiento por Longitud Descendente (Critical Path)
            # Esto asegura que "Concejal Pérez" se evalúe antes que "Pérez",
            # evitando que el reemplazo corto rompa la frase larga.
            sorted_keys = sorted(lookup_map.keys(), key=len, reverse=True)

            # 3. Construcción del Patrón Regex Seguro
            # a. Escapamos caracteres especiales (ej. "Dr.") para que sean literales.
            # b. Unimos con OR (|).
            # c. Encerramos en word boundaries (\b) para evitar el efecto "Banana" (Ana).
            pattern_str = r'\b(' + '|'.join(map(re.escape, sorted_keys)) + r')\b'

            # 4. Compilación del Regex
            # Usamos IGNORECASE para encontrar "perez", "Perez" o "PEREZ".
            pattern = re.compile(pattern_str, re.IGNORECASE)

            # 5. Función de Reemplazo (Callback)
            def replace_callback(match: re.Match) -> str:
                # El texto encontrado (puede tener cualquier casing)
                found_text = match.group(0).lower()
                # Retornamos el valor canónico del diccionario
                return lookup_map.get(found_text, match.group(0))

            # 6. Ejecución (Single Pass)
            enriched_text = pattern.sub(replace_callback, text)
            
            return enriched_text

        except Exception as e:
            # En caso de error en el regex (muy raro por el escape), devolvemos el original
            # para no romper el pipeline de producción.
            logger.error(f"Error crítico en EntityEnricher: {e}", exc_info=True)
            return text
