import logging
from typing import Dict, Optional, List, Any
from .privacy import PrivacyEngine

logger = logging.getLogger(__name__)

class DatasetBuilder:
    """
    Transforma deltas crudos en ejemplos de entrenamiento JSONL estructurados y limpios.
    """
    
    def __init__(self):
        # Intentamos inicializar el PrivacyEngine
        try:
            self.privacy = PrivacyEngine()
        except Exception as e:
            logger.error(f"DatasetBuilder no pudo inicializar el PrivacyEngine: {e}")
            self.privacy = None

    def _determine_instruction(self, metrics: Dict) -> str:
        """Selecciona el prompt del sistema basado en las métricas del cambio."""
        change_type = metrics.get("classification", "UNKNOWN")
        
        if change_type == "FIX_ORTHOGRAPHY":
            return "Corrige los errores ortográficos y de puntuación del siguiente texto administrativo."
        elif change_type == "MINOR_EDIT":
            return "Realiza ajustes menores de gramática y fluidez en el siguiente texto manteniendo el tono formal."
        elif change_type == "REPHRASE":
            return "Reescribe el siguiente texto para mejorar su formalidad y estilo administrativo, manteniendo el significado original."
        elif change_type == "MAJOR_REWRITE":
            return "Reescribe completamente el siguiente fragmento para adherirse al estándar del acta oficial."
        else:
            return "Mejora el siguiente texto para su inclusión en un acta formal."

    def build_training_row(self, delta: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Procesa un delta individual. Retorna None si el delta no es apto para entrenamiento.
        """
        original = delta.get("original_text")
        final = delta.get("final_text")
        metrics = delta.get("metrics", {})

        # Filtros de Calidad
        if not original or not final:
            return None
        
        # Ignorar si no hubo cambios
        if metrics.get("classification") == "NO_CHANGE":
            return None

        # Ignorar eliminaciones o inserciones puras
        if delta.get("alignment_method") in ["NONE", "RESIDUAL"]:
            return None

        # 1. Sanitización PII
        if self.privacy:
            sanitized_input, sanitized_output = self.privacy.sanitize_pair(original, final)
        else:
            # Si no hay privacy engine, por seguridad no generamos el dato
            return None

        if "<ERROR_PRIVACY>" in sanitized_input:
            return None

        # 2. Construcción del Objeto Instruct
        row = {
            "instruction": self._determine_instruction(metrics),
            "input": sanitized_input,
            "output": sanitized_output,
            "metadata": {
                "chunk_id": delta.get("chunk_id"),
                "wer": metrics.get("wer"),
                "classification": metrics.get("classification")
            }
        }
        
        return row
