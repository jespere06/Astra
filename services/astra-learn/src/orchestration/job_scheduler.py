import uuid
import logging
import boto3
import asyncio
from datetime import datetime
from typing import Optional

from src.infrastructure.queue_manager import QueueManager
from src.infrastructure.k8s_client import K8sClient
from src.infrastructure.clients.runpod_client import RunPodClient
from src.infrastructure.s3_datasets import S3DatasetGateway
from src.config import settings

logger = logging.getLogger(__name__)

class JobScheduler:
    def __init__(self, db_session, redis_client):
        self.db = db_session
        self.redis = redis_client
        self.queue = QueueManager(db_session)
        
        # Strategies
        self.k8s = K8sClient()
        self.runpod = RunPodClient()
        
        self.s3_gateway = S3DatasetGateway()
        # S3 client directo para presigning
        self.s3_client = boto3.client('s3') 
        
        # Umbrales
        self.BATCH_THRESHOLD = settings.BATCH_SIZE_THRESHOLD 
        self.MAX_WAIT_HOURS = settings.MAX_WAIT_HOURS 

    def _generate_presigned_url(self, key: str, method: str = 'get_object', expiration: int = 3600) -> str:
        """Genera URLs temporales para que RunPod acceda a S3."""
        try:
            # Si el key viene con prefijo s3://, limpiarlo
            clean_key = key.replace(f"s3://{settings.S3_BUCKET_NAME}/", "")
            # También manejar si viene sin el prefijo pero con el nombre del bucket al inicio
            if clean_key.startswith(settings.S3_BUCKET_NAME + "/"):
                clean_key = clean_key[len(settings.S3_BUCKET_NAME)+1:]
            
            url = self.s3_client.generate_presigned_url(
                ClientMethod=method,
                Params={
                    'Bucket': settings.S3_BUCKET_NAME,
                    'Key': clean_key
                },
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Error generando presigned URL para {key}: {e}")
            raise

    def evaluate_trigger(self, tenant_id: str):
        """
        Evalúa si se debe disparar un entrenamiento para un tenant.
        """
        # 1. Consultar estado de la cola
        count, oldest_date = self.queue.get_pending_stats(tenant_id)
        
        if count == 0:
            return

        # 2. Evaluar condiciones
        should_trigger = False
        reason = ""

        if count >= self.BATCH_THRESHOLD:
            should_trigger = True
            reason = f"Threshold reached ({count} >= {self.BATCH_THRESHOLD})"
        elif oldest_date:
            hours_waiting = (datetime.utcnow() - oldest_date).total_seconds() / 3600
            if hours_waiting >= self.MAX_WAIT_HOURS:
                should_trigger = True
                reason = f"Max wait exceeded ({hours_waiting:.1f}h >= {self.MAX_WAIT_HOURS}h)"

        if not should_trigger:
            return

        # 3. Adquirir Lock Distribuido
        lock_key = f"astra:lock:training:{tenant_id}"
        lock = self.redis.lock(lock_key, timeout=7200)

        if not lock.acquire(blocking=False):
            logger.info(f"Tenant {tenant_id}: Entrenamiento en curso. Omitiendo.")
            return

        try:
            logger.info(f"Disparando entrenamiento para {tenant_id}. Backend: {settings.TRAINING_BACKEND}. Razón: {reason}")
            
            # 4. Checkout y Preparación de Datos
            job_id_internal = f"train-{tenant_id}-{uuid.uuid4().hex[:8]}"
            batch_data = self.queue.checkout_batch(tenant_id, job_id_internal, limit=self.BATCH_THRESHOLD)
            
            if not batch_data:
                lock.release()
                return 

            # Subir dataset a S3
            dataset_s3_uri = self.s3_gateway.upload_batch(tenant_id, batch_data)
            
            # 5. Despacho según Backend
            backend = settings.TRAINING_BACKEND.upper()
            
            if backend == "RUNPOD":
                # Como el scheduler es síncrono por diseño actual, usamos un helper para disparar el async
                self._run_async(self._dispatch_runpod(job_id_internal, tenant_id, dataset_s3_uri))
            elif backend == "K8S":
                self._dispatch_k8s(job_id_internal, tenant_id, dataset_s3_uri)
            else:
                logger.error(f"Backend desconocido: {backend}. Usando K8S por defecto.")
                self._dispatch_k8s(job_id_internal, tenant_id, dataset_s3_uri)

        except Exception as e:
            logger.error(f"Fallo crítico en scheduler para {tenant_id}: {e}")
            try:
                lock.release()
            except:
                pass

    def _run_async(self, coro):
        """Helper para ejecutar corrutinas desde contexto síncrono."""
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.ensure_future(coro)
            else:
                loop.run_until_complete(coro)
        except RuntimeError:
            asyncio.run(coro)

    async def _dispatch_runpod(self, job_name: str, tenant_id: str, dataset_s3_uri: str):
        """Lógica específica para RunPod Serverless."""
        
        # Generar URLs firmadas
        # 1. Input: GET al dataset
        input_url = self._generate_presigned_url(dataset_s3_uri, 'get_object')
        
        # 2. Output: PUT para el zip del modelo
        output_key = f"models/{tenant_id}/{job_name}/adapter.zip"
        upload_url = self._generate_presigned_url(output_key, 'put_object')
        
        payload = {
            "dataset_url": input_url,
            "upload_url": upload_url,
            "validation_url": None,
            "hyperparameters": {
                "base_model": settings.BASE_MODEL_ID,
                "epochs": 3,
                "batch_size": 2,
                "max_seq_length": 2048
            }
        }
        
        try:
            external_id = await self.runpod.submit_job(payload)
            logger.info(f"🚀 Job RunPod despachado: {external_id} (Internal: {job_name})")
            
            # TODO: Guardar external_id en DB para seguimiento
            
        except Exception as e:
            logger.error(f"Error despachando a RunPod: {e}")
            raise

    def _dispatch_k8s(self, job_name: str, tenant_id: str, dataset_s3_uri: str):
        """Lógica legacy para K8s."""
        self.k8s.create_training_job(
            job_name=job_name,
            tenant_id=tenant_id,
            dataset_uri=dataset_s3_uri,
            base_model=settings.BASE_MODEL_ID
        )
