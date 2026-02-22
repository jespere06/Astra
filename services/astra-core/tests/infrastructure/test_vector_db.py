import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.infrastructure.vector_db import VectorDBClient, settings

class TestVectorDB:
    @pytest.fixture
    def mock_qdrant_client(self):
        # Mock de la clase AsyncQdrantClient
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_search_isolation(self, mock_qdrant_client):
        """
        DoD: La búsqueda debe fallar/retornar vacío si no hay tenant_id.
        """
        # Como no tenemos qdrant instalado en el agente, mockeamos la libreria
        with patch("src.infrastructure.vector_db.AsyncQdrantClient", return_value=mock_qdrant_client):
            client = VectorDBClient()
            client.client = mock_qdrant_client # Asegurar que usa el mock

            # Ejecutar búsqueda sin tenant
            results = await client.search(
                vector=[0.1] * 768, 
                tenant_id=""
            )
            
            # Debe retornar vacío por seguridad
            assert results == []

    @pytest.mark.asyncio
    async def test_search_execution(self, mock_qdrant_client):
        """
        DoD: Verificar llamada correcta a qdrant.search con filtros.
        """
        
        # Simulamos respuesta de Qdrant
        mock_hit = MagicMock()
        mock_hit.id = "uuid-123"
        mock_hit.score = 0.95
        mock_hit.payload = {"template_name": "Acta Plenaria"}
        
        mock_qdrant_client.search.return_value = [mock_hit]

        with patch("src.infrastructure.vector_db.AsyncQdrantClient", return_value=mock_qdrant_client):
            client = VectorDBClient()
            client.client = mock_qdrant_client

            results = await client.search(
                vector=[0.1] * 768, 
                tenant_id="tenant-A"
            )

            assert len(results) == 1
            assert results[0]["id"] == "uuid-123"
            assert results[0]["payload"]["template_name"] == "Acta Plenaria"
            
            # Verificar argumentos de llamada (especialmente el filtro)
            mock_qdrant_client.search.assert_called_once()
            call_kwargs = mock_qdrant_client.search.call_args.kwargs
            
            assert call_kwargs["collection_name"] == settings.QDRANT_COLLECTION
            assert "query_filter" in call_kwargs
