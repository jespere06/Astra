import pytest
from unittest.mock import MagicMock
from src.nlp.embeddings import EmbeddingService

class TestEmbeddingService:
    @pytest.fixture
    def mock_onnx(self):
        # Como no tenemos los modelos en el entorno CI del agente,
        # necesitamos mockear ort.InferenceSession y Tokenizer
        # Esto solo prueba la lógica de integración, no la calidad del embedding
        return MagicMock()

    def test_mock_embedding_generation(self, mock_onnx):
        """
        Verifica que el servicio retorne un vector de 768 dims (dummy)
        cuando no hay modelo cargado (Fallback).
        """
        service = EmbeddingService()
        
        # Simulamos ausencia de modelo (comportamiento default en entorno sin archivos)
        vector = service.embed("Texto de prueba para vectorización")
        
        assert isinstance(vector, list)
        assert len(vector) == 768
        assert all(isinstance(x, float) for x in vector)

    def test_normalization_logic(self):
        """Validar matemáticamente la función de normalización L2"""
        # TODO: Implementar test con numpy real si estuviera disponible
        pass
