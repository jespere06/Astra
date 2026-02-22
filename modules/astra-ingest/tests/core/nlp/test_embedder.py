import pytest
import numpy as np
from unittest.mock import MagicMock, patch
from src.core.nlp.embedder import TextEmbedder

class TestTextEmbedder:

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        """Resetea el Singleton antes de cada test para aislamiento."""
        TextEmbedder._instance = None
        TextEmbedder._model = None
        TextEmbedder._device = None

    def test_singleton_pattern(self):
        """Verifica que múltiples instanciaciones retornen el mismo objeto."""
        embedder1 = TextEmbedder()
        embedder2 = TextEmbedder()
        
        assert embedder1 is embedder2
        assert id(embedder1) == id(embedder2)

    @patch("src.core.nlp.embedder.torch")
    @patch("src.core.nlp.embedder.SentenceTransformer")
    def test_lazy_loading_and_device_selection_cuda(self, mock_transformer, mock_torch):
        """Verifica carga perezosa y selección de CUDA."""
        # Configurar mocks
        mock_torch.cuda.is_available.return_value = True
        mock_transformer_instance = MagicMock()
        mock_transformer.return_value = mock_transformer_instance
        
        embedder = TextEmbedder()
        
        # Al instanciar NO debe haber cargado el modelo aún
        assert embedder.is_loaded is False
        assert mock_transformer.call_count == 0
        
        # Ejecutar inferencia (trigger lazy load)
        embedder.embed_batch(["test"])
        
        # Verificar carga
        assert embedder.is_loaded is True
        mock_transformer.assert_called_once_with(
            TextEmbedder.MODEL_NAME, 
            device="cuda"
        )
        assert embedder.device == "cuda"

    @patch("src.core.nlp.embedder.torch")
    @patch("src.core.nlp.embedder.SentenceTransformer")
    def test_device_fallback_cpu(self, mock_transformer, mock_torch):
        """Verifica fallback a CPU si no hay aceleradores."""
        mock_torch.cuda.is_available.return_value = False
        mock_torch.backends.mps.is_available.return_value = False
        
        embedder = TextEmbedder()
        embedder._load_model()
        
        assert embedder.device == "cpu"
        mock_transformer.assert_called_with(TextEmbedder.MODEL_NAME, device="cpu")

    @patch("src.core.nlp.embedder.SentenceTransformer")
    def test_embed_batch_output_structure(self, mock_transformer):
        """Verifica dimensiones y tipos de datos del output."""
        # Simular output de SentenceTransformer (numpy array)
        # 2 textos, 768 dimensiones
        dummy_embeddings = np.random.rand(2, 768).astype(np.float32)
        
        mock_instance = MagicMock()
        mock_instance.encode.return_value = dummy_embeddings
        mock_transformer.return_value = mock_instance
        
        embedder = TextEmbedder()
        input_texts = ["Hola mundo", "Astra AI"]
        
        result = embedder.embed_batch(input_texts)
        
        # Verificar llamada correcta a la librería
        mock_instance.encode.assert_called_once_with(
            input_texts,
            batch_size=32,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True
        )
        
        # Verificar resultado
        assert isinstance(result, list)
        assert len(result) == 2
        assert isinstance(result[0], list)
        assert len(result[0]) == 768
        assert isinstance(result[0][0], float)

    def test_empty_input(self):
        """Verifica manejo de listas vacías."""
        embedder = TextEmbedder()
        # No mockeamos el modelo porque con input vacío no debería llegar a cargarlo/usarlo
        result = embedder.embed_batch([])
        assert result == []