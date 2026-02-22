import pytest
import respx
from httpx import Response
from src.infrastructure.clients.runpod_client import RunPodClient, RunPodError
from src.config import settings
from unittest.mock import patch

# Mock configuration
settings.RUNPOD_API_KEY = "test-key"
settings.RUNPOD_ENDPOINT_ID = "test-endpoint"

@pytest.fixture
def client():
    return RunPodClient()

@pytest.mark.asyncio
@respx.mock
async def test_submit_job_success(client):
    """Verifica que se envíe el payload correcto y se extraiga el ID."""
    endpoint = f"https://api.runpod.ai/v2/{settings.RUNPOD_ENDPOINT_ID}/run"
    
    mock_response = {
        "id": "job-123",
        "status": "IN_QUEUE"
    }
    
    route = respx.post(endpoint).mock(return_value=Response(200, json=mock_response))
    
    input_data = {"dataset": "s3://bucket/data.csv", "epochs": 3}
    job_id = await client.submit_job(input_data)
    
    assert job_id == "job-123"
    
    # Verificar que el payload se envolvió en "input"
    last_request = route.calls.last.request
    import json
    body = json.loads(last_request.content)
    assert "input" in body
    assert body["input"]["dataset"] == "s3://bucket/data.csv"
    assert last_request.headers["Authorization"] == "Bearer test-key"

@pytest.mark.asyncio
@respx.mock
async def test_submit_job_error_401(client):
    """Verifica el manejo de errores de autenticación."""
    endpoint = f"https://api.runpod.ai/v2/{settings.RUNPOD_ENDPOINT_ID}/run"
    
    respx.post(endpoint).mock(return_value=Response(401, json={"error": "Unauthorized"}))
    
    with pytest.raises(RunPodError) as exc:
        await client.submit_job({"test": "data"})
    
    assert "Error de cliente RunPod" in str(exc.value)

@pytest.mark.asyncio
@respx.mock
async def test_get_status_success(client):
    """Verifica la consulta de estado."""
    job_id = "job-123"
    endpoint = f"https://api.runpod.ai/v2/{settings.RUNPOD_ENDPOINT_ID}/status/{job_id}"
    
    mock_response = {
        "id": job_id,
        "status": "COMPLETED",
        "output": {"model_url": "s3://bucket/model.bin"}
    }
    
    respx.get(endpoint).mock(return_value=Response(200, json=mock_response))
    
    status = await client.get_status(job_id)
    assert status["status"] == "COMPLETED"
    assert status["output"]["model_url"] == "s3://bucket/model.bin"

@pytest.mark.asyncio
@respx.mock
async def test_cancel_job_success(client):
    """Verifica la cancelación."""
    job_id = "job-123"
    endpoint = f"https://api.runpod.ai/v2/{settings.RUNPOD_ENDPOINT_ID}/cancel/{job_id}"
    
    respx.post(endpoint).mock(return_value=Response(200, json={"status": "CANCELLED"}))
    
    result = await client.cancel_job(job_id)
    assert result is True

@pytest.mark.asyncio
@respx.mock
async def test_retry_mechanism(client):
    """Verifica que se reintenta ante errores de servidor (500)."""
    endpoint = f"https://api.runpod.ai/v2/{settings.RUNPOD_ENDPOINT_ID}/run"
    
    # Simular 2 fallos 500 y luego éxito
    route = respx.post(endpoint).mock(
        side_effect=[
            Response(500),
            Response(502),
            Response(200, json={"id": "job-retry"})
        ]
    )
    
    # Reducimos el sleep para que el test no tarde
    with patch("asyncio.sleep", return_value=None): 
        job_id = await client.submit_job({})
    
    assert job_id == "job-retry"
    assert route.call_count == 3
