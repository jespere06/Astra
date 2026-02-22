import logging
from typing import List
from src.config import settings

logger = logging.getLogger(__name__)

class EmbeddingService:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EmbeddingService, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        # Ya no cargamos onnxruntime ni torch
        logger.info("⚡ MODO LIGERO: Usando Mock Embeddings (Local Dev)")

    def embed(self, text: str) -> List[float]:
        """
        Retorna un vector dummy de 768 dimensiones.
        En PROD/RunPod, esto usará la implementación real o OpenAI.
        """
        return [0.1] * 768

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Retorna una lista de vectores dummy.
        """
        return [[0.1] * 768 for _ in texts]
