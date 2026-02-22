import logging
try:
    from rapidfuzz import fuzz
except ImportError:
    # Fallback if not installed
    fuzz = None
    
from typing import Dict, Any, Tuple

from src.config import get_settings
from src.nlp.embeddings import EmbeddingService
from src.infrastructure.qdrant_adapter import QdrantAdapter
from src.logic.table_parser import TableParser
from src.generated.astra_models_pb2 import IntentType # Asumiendo DTO generado o Mock

logger = logging.getLogger(__name__)

class IntentClassifier:
    def __init__(self):
        self.settings = get_settings()
        self.embedder = EmbeddingService() # Corrigiendo nombre de clase
        self.qdrant = QdrantAdapter()
        self.table_parser = TableParser()

    def classify(self, clean_text: str, tenant_id: str) -> Dict[str, Any]:
        """
        Clasifica el texto y extrae metadatos.
        
        Returns:
            Dict con: intent, template_id, confidence, structured_data, metadata
        """
        # 0. Default: Texto Libre
        result = {
            "intent": IntentType.INTENT_FREE_TEXT,
            "template_id": "",
            "confidence": 0.0,
            "structured_data": [],
            "metadata": {}
        }

        if not clean_text:
            return result

        # 1. Vectorización (EmbeddingsService returns single vector for embed)
        # Using [0] to match original logic, assuming embed returns a single list of floats
        vector = self.embedder.embed(clean_text)

        # 2. Búsqueda Vectorial (Segura por Tenant)
        match = self.qdrant.search_best_match(vector, tenant_id)

        if not match:
            logger.debug(f"No match found for tenant {tenant_id}")
            return result

        # Evaluar Score Vectorial
        if match.score < self.settings.SIMILARITY_THRESHOLD:
            logger.debug(f"Match score {match.score} below threshold {self.settings.SIMILARITY_THRESHOLD}")
            return result

        # Recuperar Payload
        payload = match.payload
        template_text = payload.get("preview_text", "")
        # is_boilerplate = payload.get("is_boilerplate", False)
        variables = payload.get("variables_metadata", []) # Lista de nombres de vars

        # 3. Lógica Híbrida (Comparación de Texto)
        text_similarity = 0
        if fuzz:
            # Ratio de similitud textual (0-100)
            text_similarity = fuzz.ratio(clean_text.lower(), template_text.lower())
        else:
            logger.warning("Rapidfuzz not installed. Skipping text similarity check.")
        
        # Determinación de Intención
        intent_type = IntentType.INTENT_FREE_TEXT
        
        if text_similarity >= self.settings.EXACT_MATCH_THRESHOLD:
            intent_type = IntentType.INTENT_TEMPLATE
        elif text_similarity >= self.settings.HYBRID_MATCH_THRESHOLD:
            intent_type = IntentType.INTENT_HYBRID
        elif match.score > 0.92: 
            # Alta confianza vectorial aunque el texto varíe (ej. muchas variables)
            intent_type = IntentType.INTENT_TEMPLATE
        else:
            # Zona gris: Vector dice sí, texto dice no -> Preferir FREE_TEXT o HYBRID
            # Si el vector es fuerte (SIMILARITY_THRESHOLD < score < 0.92) pero texto difiere
            # lo marcamos como Hibrido para revisor humano o fallback
            intent_type = IntentType.INTENT_HYBRID

        if intent_type in [IntentType.INTENT_TEMPLATE, IntentType.INTENT_HYBRID]:
            # Extracción antigua comentada o eliminada, delegada al Pipeline
            # structured_data = ...
            pass

        # 5. Construcción de Respuesta
        result.update({
            "intent": intent_type,
            "template_id": payload.get("id"), # UUID del template en DB
            "confidence": float(match.score),
            "structured_data": structured_data,
            "metadata": {
                "vector_score": str(match.score),
                "text_similarity": str(text_similarity),
                "structure_hash": payload.get("structure_hash", ""),
                "cluster_source": payload.get("cluster_source_id", ""),
                "variables": variables
            }
        })
        
        logger.info(f"Classified: {intent_type} (Score: {match.score:.4f}, Levenshtein: {text_similarity})")
        return result
