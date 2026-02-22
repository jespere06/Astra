import pytest
from unittest.mock import AsyncMock, MagicMock
from src.services.processor import TrainingProcessor
from src.schemas.job_dtos import TrainingJobRequest, ExecutionMode, JobStatus

@pytest.fixture
def mock_deps():
    job_repo = AsyncMock()
    mining_client = AsyncMock()
    runpod_client = AsyncMock()
    
    # Configurar respuesta exitosa del miner
    mining_client.run_mining_pipeline.return_value = {
        "dataset_s3_url": "s3://bucket/train.jsonl",
        "alignment_stats": {"total_segments": 150, "aligned_pairs": 142}
    }
    
    # Configurar respuesta exitosa de RunPod
    runpod_client.dispatch_job.return_value = {
        "id": "runpod-123",
        "status": "IN_QUEUE"
    }
    
    return job_repo, mining_client, runpod_client

@pytest.mark.asyncio
async def test_data_prep_only_short_circuit(mock_deps):
    """
    Verifica que en modo DATA_PREP_ONLY el orquestador NO invoque a RunPod.
    Criterio de éxito T10.
    """
    job_repo, mining_client, runpod_client = mock_deps
    processor = TrainingProcessor(job_repo, mining_client, runpod_client)
    
    req = TrainingJobRequest(
        tenant_id="test", 
        source_urls=["http://yt.com/video"], 
        execution_mode=ExecutionMode.DATA_PREP_ONLY
    )
    
    await processor.process_training_request("job-001", req)
    
    # 1. Verificar que se llamó a Minería
    mining_client.run_mining_pipeline.assert_called_once()
    
    # 2. Verificar que NUNCA se llamó a RunPod (Short-circuit)
    runpod_client.dispatch_job.assert_not_called()
    
    # 3. Verificar estado final en DB
    job_repo.complete_job.assert_called_once()
    args = job_repo.complete_job.call_args
    assert args[0][0] == "job-001"
    assert args[0][1]["status"] == "SKIPPED_TRAINING"

@pytest.mark.asyncio
async def test_full_training_flow(mock_deps):
    """
    Verifica que en modo FULL_TRAINING el flujo continúe hasta RunPod.
    """
    job_repo, mining_client, runpod_client = mock_deps
    processor = TrainingProcessor(job_repo, mining_client, runpod_client)
    
    req = TrainingJobRequest(
        tenant_id="test", 
        source_urls=["http://yt.com/video"], 
        execution_mode=ExecutionMode.FULL_TRAINING
    )
    
    await processor.process_training_request("job-002", req)
    
    # 1. Verificar Minería
    mining_client.run_mining_pipeline.assert_called_once()
    
    # 2. Verificar Despacho a RunPod (NO hubo short-circuit)
    runpod_client.dispatch_job.assert_called_once()
    
    # 3. Verificar persistencia de ID externo
    job_repo.update_external_id.assert_called_with("job-002", "runpod-123")