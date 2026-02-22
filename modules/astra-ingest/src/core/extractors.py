import re
import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)

class EntityExtractor:
    """
    Extractor heurístico basado en Regex para identificar entidades 
    comunes en actas municipales (Concejales, Barrios, Cargos).
    """

    # Patrones para capturar nombres después de títulos comunes
    PATTERNS = {
        "CONCEJAL": [
            r"(?:Honorable\s+Concejal|H\.C\.)\s+([A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+){1,3})",
            r"(?:Concejal)\s+([A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+){1,3})"
        ],
        "SECRETARIO": [
            r"(?:Secretario|Secretaria)\s+([A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+){1,3})"
        ],
        "BARRIO": [
            r"(?:Barrio|Vereda)\s+([A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+){0,2})"
        ],
        "ALCALDE": [
            r"(?:Alcalde|Alcaldesa)\s+([A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-zaréíóúñ]+){1,3})"
        ]
    }

    def __init__(self):
        self.compiled_patterns = {
            k: [re.compile(p) for p in v] 
            for k, v in self.PATTERNS.items()
        }
        # Lista negra para evitar falsos positivos comunes
        self.blacklist = {
            "El", "La", "Los", "Las", "Del", "Al", "Un", "Una", 
            "Presidente", "Secretario", "Concejal", "Manizales", "Caldas"
        }

    def extract_entities(self, text: str) -> Dict[str, str]:
        """
        Analiza el texto y retorna un diccionario de candidatos.
        Retorna: {"Nombre Detectado": "Cargo/Tipo Detectado"}
        Ej: {"Juan Perez": "CONCEJAL"}
        """
        found_entities = {}

        if not text or len(text) < 20:
            return {}

        for entity_type, regex_list in self.compiled_patterns.items():
            for regex in regex_list:
                matches = regex.findall(text)
                for match in matches:
                    entity_name = match.strip()
                    
                    # Validaciones básicas
                    if len(entity_name) < 4: 
                        continue
                    if entity_name in self.blacklist:
                        continue
                    
                    # Guardamos. Si ya existe, prevalece.
                    if entity_name not in found_entities:
                        found_entities[entity_name] = entity_type

        return found_entities

    def merge_dictionaries(self, current_dict: Dict, new_dict: Dict) -> Dict:
        """Fusiona nuevos hallazgos con el diccionario existente."""
        # En una implementación real, aquí podríamos tener lógica de resolución de conflictos
        # Por ahora, simplemente agregamos lo nuevo.
        merged = current_dict.copy()
        for name, type_ in new_dict.items():
            # Solo agregamos si no existe, para preservar correcciones manuales previas
            if name not in merged:
                # Guardamos en formato Key=Nombre, Value=Forma Canónica sugerida
                # Ej: "juan perez" -> "H.C. Juan Perez"
                prefix = "H.C." if type_ == "CONCEJAL" else type_.capitalize()
                merged[name] = f"{prefix} {name}"
        return merged
