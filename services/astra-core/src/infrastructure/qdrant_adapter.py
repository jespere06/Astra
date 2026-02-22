import logging
from typing import List, Optional, Dict, Any
try:
    from qdrant_client import QdrantClient
    from qdrant_client.http import models
except ImportError:
    # Fallback to prevent crash if not installed
    print("Warning: qdrant-client not installed.")
    QdrantClient = None
    models = None

from src.config import get_settings

logger = logging.getLogger(__name__)

class QdrantAdapter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(QdrantAdapter, cls).__new__(cls)
            cls._instance._init_client()
        return cls._instance

    def _init_client(self):
        settings = get_settings()
        if QdrantClient:
            self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
            self.collection_name = settings.QDRANT_COLLECTION
        else:
            self.client = None

    def search_best_match(self, vector: List[float], tenant_id: str) -> Optional[Any]:
        """
        Busca el vector más cercano garantizando aislamiento por tenant.
        """
        if not self.client:
            return None

        try:
            # Filtro de seguridad obligatorio
            tenant_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="tenant_id",
                        match=models.MatchValue(value=tenant_id)
                    )
                ]
            )

            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                query_filter=tenant_filter,
                limit=1,
                with_payload=True
            )

            if not results:
                return None
            
            return results[0]

        except Exception as e:
            logger.error(f"Error consultando Qdrant: {e}")
            return None

    def index_template(self, tenant_id: str, template_id: str, text: str, metadata: Dict, vector: List[float]) -> bool:
        """
        Inserta o actualiza un template en Qdrant.
        """
        if not self.client:
            return False
            
        try:
            # Asegurar que el tenant_id viaja en el payload para filtrar
            metadata["tenant_id"] = tenant_id 
            
            p = models.PointStruct(
                id=template_id, # UUID si es posible, o hash determinista
                vector=vector,
                payload=metadata
            )
            
            self.client.upsert(
                collection_name=self.collection_name,
                points=[p]
            )
            return True
        except Exception as e:
            logger.error(f"Error indexando en Qdrant: {e}")
            return False
