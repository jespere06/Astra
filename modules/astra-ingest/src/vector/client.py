from qdrant_client import QdrantClient
from src.config import settings

def get_qdrant_client() -> QdrantClient:
    """Retorna una instancia configurada del cliente Qdrant."""
    return QdrantClient(url=settings.QDRANT_URL)