import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.logic.scheduler import ResourceGovernor
from src.asr.manager import ProviderManager
from src.schemas.qos_models import TaskPriority, ProcessingStatus
from openai import RateLimitError

@pytest.mark.asyncio
async def test_scheduler_failover_flow():
    # Setup Mocks
    mock_saas = AsyncMock()
    mock_saas.transcribe.side_effect = RateLimitError("Rate limit exceeded", response=MagicMock(), body=None)
    
    mock_local = AsyncMock()
    mock_local.transcribe.return_value = "Texto local"
    
    manager = ProviderManager(mock_saas, mock_local)
    
    # Mock S3 para evitar errores de credenciales reales
    with patch("boto3.client"):
        governor = ResourceGovernor(manager)
        
        # Ejecución
        result = await governor.process_request(b"audio", TaskPriority.LIVE_SESSION, "tenant_1")
        
        # Verificaciones
        assert result.text == "Texto local"
        assert result.status == ProcessingStatus.COMPLETED
        assert result.qos_meta.provider_used == "local"
        assert result.qos_meta.failover_occurred is True

@pytest.mark.asyncio
async def test_scheduler_total_failure():
    # Setup: Ambos fallan
    mock_saas = AsyncMock()
    mock_saas.transcribe.side_effect = Exception("SaaS Down")
    
    mock_local = AsyncMock()
    mock_local.transcribe.side_effect = Exception("Local GPU OOM")
    
    manager = ProviderManager(mock_saas, mock_local)
    
    with patch("boto3.client") as mock_boto:
        mock_s3 = MagicMock()
        mock_boto.return_value = mock_s3
        
        governor = ResourceGovernor(manager)
        result = await governor.process_request(b"audio", TaskPriority.LIVE_SESSION, "tenant_1")
        
        # Verificaciones
        assert result.status == ProcessingStatus.AUDIO_PENDING
        assert result.qos_meta.s3_fallback_url is not None
        mock_s3.put_object.assert_called_once() # Se intentó guardar en S3
