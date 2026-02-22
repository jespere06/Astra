import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import os
import asyncio
from src.orchestration.job_scheduler import JobScheduler
from src.config import settings

class TestJobSchedulerSwitch:
    
    @pytest.fixture
    def mock_deps(self):
        db = MagicMock()
        redis = MagicMock()
        # Mock del Lock de Redis
        lock = MagicMock()
        lock.acquire.return_value = True
        redis.lock.return_value = lock
        
        return db, redis

    @pytest.fixture
    def scheduler(self, mock_deps):
        db, redis = mock_deps
        # Patch interno de componentes
        with patch("src.orchestration.job_scheduler.QueueManager") as MockQueue, \
             patch("src.orchestration.job_scheduler.K8sClient") as MockK8s, \
             patch("src.orchestration.job_scheduler.RunPodClient") as MockRunPod, \
             patch("src.orchestration.job_scheduler.S3DatasetGateway") as MockS3Gate, \
             patch("src.orchestration.job_scheduler.boto3.client") as MockBoto:
            
            sched = JobScheduler(db, redis)
            
            # Setup defaults
            sched.queue.get_pending_stats.return_value = (1000, None) # Trigger por threshold
            sched.queue.checkout_batch.return_value = [{"id": 1}]
            sched.s3_gateway.upload_batch.return_value = "s3://astra-models/data.jsonl"
            sched.s3_client.generate_presigned_url.return_value = "https://s3-signed-url.com"
            
            # Mock Async methods
            sched.runpod.submit_job = AsyncMock(return_value="rp-job-123")
            
            return sched

    def test_dispatch_k8s_branch(self, scheduler):
        """Verifica que se llame a K8s cuando el backend es K8S."""
        with patch.object(settings, "TRAINING_BACKEND", "K8S"):
            scheduler.evaluate_trigger("tenant-1")
            
            scheduler.k8s.create_training_job.assert_called_once()
            # Verificar que RunPod NO se llamó
            scheduler.runpod.submit_job.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_runpod_branch(self, scheduler):
        """Verifica que se llame a RunPod cuando el backend es RUNPOD."""
        with patch.object(settings, "TRAINING_BACKEND", "RUNPOD"):
            # Mock de _run_async para capturar la corrutina
            with patch.object(scheduler, "_run_async") as mock_run_async:
                scheduler.evaluate_trigger("tenant-1")
                mock_run_async.assert_called_once()
                
                # Ejecutar la corrutina capturada para probar la lógica interna
                coro = mock_run_async.call_args[0][0]
                await coro
                
                # Verificar generación de URLs firmadas
                assert scheduler.s3_client.generate_presigned_url.call_count == 2
                
                # Verificar llamada al cliente RunPod
                scheduler.runpod.submit_job.assert_called_once()
                
                # Verificar Payload
                call_args = scheduler.runpod.submit_job.call_args[0][0]
                assert call_args["dataset_url"] == "https://s3-signed-url.com"
                assert call_args["upload_url"] == "https://s3-signed-url.com"

    def test_evaluate_trigger_no_data(self, scheduler):
        """Verifica que NO se dispare si no hay datos."""
        scheduler.queue.get_pending_stats.return_value = (0, None)
        
        scheduler.evaluate_trigger("tenant-1")
        
        scheduler.k8s.create_training_job.assert_not_called()
        scheduler.runpod.submit_job.assert_not_called()
