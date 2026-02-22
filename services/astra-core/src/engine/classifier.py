import logging
from typing import Tuple, Dict
from qdrant_client import QdrantClient
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from src.config import settings

logger = logging.getLogger(__name__)

class IntentResolver:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IntentResolver, cls).__new__(cls)
            cls._instance._init_resources()
        return cls._instance

    def _init_resources(self):
        logger.info("🔄 Cargando modelo de Embeddings y Cliente Qdrant...")
        self.embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
        self.qdrant = QdrantClient(url=settings.QDRANT_URL)
        logger.info("✅ Recursos de clasificación listos.")

    def classify(self, text: str, tenant_id: str) -> Tuple[str, float, Dict]:
        """
        Retorna: (IntentType, Confidence, Metadata)
        IntentType: 'PLANTILLA' | 'LIBRE'
        """
        if not text.strip():
            return "LIBRE", 0.0, {}

        # 1. Vectorizar
        vector = self.embedder.encode(text).tolist()

        # 2. Buscar en Qdrant con filtro de Tenant
        search_result = self.qdrant.search(
            collection_name=settings.QDRANT_COLLECTION,
            query_vector=vector,
            query_filter=models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_id",
                        match=models.MatchValue(value=tenant_id)
                    )
                ]
            ),
            limit=1
        )

        if not search_result:
            return "LIBRE", 0.0, {}

        best_match = search_result[0]
        
        # 3. Decisión basada en Umbral
        if best_match.score >= settings.INTENT_THRESHOLD:
            # Es una plantilla
            payload = best_match.payload or {}
            metadata = {
                "template_id": payload.get("template_id", "unknown"),
                "structure_hash": payload.get("structure_hash", ""),
                "original_match_score": best_match.score
            }
            return "PLANTILLA", best_match.score, metadata
        else:
            return "LIBRE", best_match.score, {}
