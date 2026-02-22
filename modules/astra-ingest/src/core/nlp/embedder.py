import logging
import torch
import threading  # <--- NUEVO IMPORT
from typing import List, Optional
from sentence_transformers import SentenceTransformer

# Configuración de Logging
logger = logging.getLogger(__name__)

class TextEmbedder:
    """
    Componente central de vectorización de texto.
    Implementa patrón Singleton para evitar recargas del modelo.
    Modelo base: paraphrase-multilingual-mpnet-base-v2 (768 dim).
    """
    
    _instance: Optional['TextEmbedder'] = None
    _model: Optional[SentenceTransformer] = None
    _device: Optional[str] = None
    
    # <--- NUEVO: Semáforo para evitar el "Already borrowed" de Rust
    _lock = threading.Lock() 
    
    # Nombre del modelo en HuggingFace Hub
    MODEL_NAME = "paraphrase-multilingual-mpnet-base-v2"

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TextEmbedder, cls).__new__(cls)
        return cls._instance

    def _detect_device(self) -> str:
        """Determina el dispositivo de hardware más rápido disponible."""
        if self._device:
            return self._device
            
        if torch.cuda.is_available():
            device = "cuda"
        elif torch.backends.mps.is_available():
            # Soporte para Apple Silicon (M1/M2/M3)
            device = "mps" 
        else:
            device = "cpu"
            
        self._device = device
        return device

    def _load_model(self):
        """Carga el modelo en memoria (Lazy Loading)."""
        if self._model is not None:
            return

        device = self._detect_device()
        logger.info(f"🔄 Cargando modelo NLP '{self.MODEL_NAME}' en dispositivo: {device.upper()}...")
        
        try:
            self._model = SentenceTransformer(self.MODEL_NAME, device=device)
            logger.info(f"✅ Modelo NLP cargado exitosamente en {device.upper()}.")
        except Exception as e:
            logger.critical(f"❌ Error fatal cargando modelo NLP: {e}")
            raise RuntimeError(f"No se pudo cargar el modelo de embeddings: {e}")

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Genera embeddings vectoriales para una lista de textos.
        
        Args:
            texts: Lista de strings a vectorizar.
            batch_size: Tamaño del lote para procesamiento interno.
            
        Returns:
            Lista de listas de floats (Vectores de 768 dimensiones).
        """
        # Validación de entrada
        if not texts:
            return []

        # Asegurar que el modelo esté cargado de forma segura entre hilos
        if self._model is None:
            with self._lock:  # <--- NUEVO
                if self._model is None:
                    self._load_model()

        try:
            # sentence-transformers maneja el batching y tokenization internamente
            # normalize_embeddings=True es crítico para búsquedas por similitud de coseno
            
            # <--- NUEVO: Bloqueamos el uso del modelo para evitar colisiones de memoria en el Mac
            with self._lock:
                embeddings = self._model.encode(
                    texts,
                    batch_size=batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                    normalize_embeddings=True
                )
            
            # Convertir numpy array a lista nativa de Python (serializable)
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"Error generando embeddings para batch de tamaño {len(texts)}: {e}")
            raise

    @property
    def is_loaded(self) -> bool:
        """Verifica si el modelo ya está en memoria."""
        return self._model is not None

    @property
    def device(self) -> str:
        """Retorna el dispositivo actual del modelo."""
        return self._detect_device()