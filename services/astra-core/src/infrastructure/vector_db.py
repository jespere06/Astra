import logging
import asyncio
from typing import List, Dict, Any

try:
    from qdrant_client import AsyncQdrantClient
    from qdrant_client.http import models as rest
except ImportError:
    # Fallack para evitar crash en setup parcial
    AsyncQdrantClient = None
    rest = None

from src.config import settings

logger = logging.getLogger(__name__)

class VectorDBClient:
    """Wrapper para operaciones sobre Qdrant con aislamiento por Tenant."""
    
    def __init__(self):
        if not AsyncQdrantClient:
            logger.warning("Qdrant Client no instalado.")
            return

        self.client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
        # Colección principal de conocimiento ASTRA
        self.collection_name = settings.QDRANT_COLLECTION

    async def ensure_collection(self):
        """Verifica y crea la colección si no existe (al inicio del servicio)."""
        if not self.client: return
        
        try:
            collections = await self.client.get_collections()
            exists = any(c.name == self.collection_name for c in collections.collections)
            
            if not exists:
                logger.info(f"Creando colección Qdrant: {self.collection_name}")
                await self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=rest.VectorParams(size=768, distance=rest.Distance.COSINE),
                    # Optimizadores HNSW default
                )
        except Exception as e:
            logger.error(f"Fallo conectando a Qdrant: {e}")

    async def search(self, vector: List[float], tenant_id: str, limit: int = 3, score_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """
        Búsqueda semántica filtrada por tenant_id.
        Retorna payloads de los items más cercanos.
        """
        if not self.client:
            logger.warning("VectorDB inactiva. Retornando vacío.")
            return []

        if not tenant_id:
            logger.error("Intento de búsqueda vectorial sin tenant_id. Seguridad comprometida.")
            return []

        try:
            # Filtro Obligatorio de Tenant (Aislamiento)
            search_filter = rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="tenant_id",
                        match=rest.MatchValue(value=tenant_id)
                    )
                ]
            )

            results = await self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=search_filter,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Serializar resultados
            return [
                {
                    "id": hit.id,
                    "score": hit.score,
                    "payload": hit.payload
                } 
                for hit in results
            ]

        except Exception as e:
            logger.error(f"Error en búsqueda vectorial: {e}")
            return []

    async def store_embedding(self, tenant_id: str, vector: List[float], metadata: Dict[str, Any]):
        """Almacena un nuevo vector (Template/Knowledge)"""
        # (Implementación futura para COR-04: Registrar plantillas)
        pass
