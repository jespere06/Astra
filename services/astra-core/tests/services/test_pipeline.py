import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.services.pipeline import SemanticPipeline
from src.schemas.process import ProcessingRequest
from src.generated.astra_models_pb2 import IntentType

@pytest.mark.asyncio
async def test_pipeline_e2e_text_flow():
    # Setup Mocks
    with patch("src.services.pipeline.TextSanitizer") as mock_sanitizer, \
         patch("src.services.pipeline.IntentClassifier") as mock_classifier, \
         patch("src.services.pipeline.EntityEnricher") as mock_enricher:
        
        # Configurar comportamientos
        mock_sanitizer.return_value.clean.return_value = "Texto limpio"
        mock_classifier.return_value.classify.return_value = {
            "intent": IntentType.INTENT_FREE_TEXT,
            "confidence": 0.8,
            "template_id": "",
            "structured_data": None,
            "metadata": {}
        }
        mock_enricher.return_value.apply.return_value = "Texto enriquecido"

        pipeline = SemanticPipeline()
        
        req = ProcessingRequest(
            tenant_id="test_tenant",
            text_content="Texto sucio",
            client_timezone="America/Bogota"
        )

        # Ejecución
        result = await pipeline.execute(req)

        # Verificaciones
        assert result.clean_text == "Texto enriquecido"
        assert result.processed_at.endswith("-05:00") # Bogota Offset
        assert result.warnings == []
        
        mock_sanitizer.return_value.clean.assert_called_once()
        mock_classifier.return_value.classify.assert_called_with("Texto limpio", "test_tenant")
        mock_enricher.return_value.apply.assert_called_once()
