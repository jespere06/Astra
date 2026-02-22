import os
import logging
from typing import Optional, Dict, Any
import mlflow
from mlflow.tracking import MlflowClient as OriginalClient
from mlflow.entities import RunStatus

logger = logging.getLogger(__name__)

class ModelRegistryClient:
    """
    Wrapper para MLflow que gestiona el registro de modelos y experimentos
    con aislamiento lógico por Tenant.
    """

    def __init__(self, tracking_uri: str = None):
        self.tracking_uri = tracking_uri or os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
        mlflow.set_tracking_uri(self.tracking_uri)
        self.client = OriginalClient(tracking_uri=self.tracking_uri)
        
        # S3 Endpoint setup si estamos usando MinIO localmente
        if os.getenv("MLFLOW_S3_ENDPOINT_URL"):
            os.environ["MLFLOW_S3_ENDPOINT_URL"] = os.getenv("MLFLOW_S3_ENDPOINT_URL")

    def setup_tenant_experiment(self, tenant_id: str) -> str:
        """
        Crea o recupera un Experimento de MLflow específico para un inquilino.
        Naming convention: astra/tenant_{id}
        """
        experiment_name = f"astra/tenant_{tenant_id}"
        experiment = self.client.get_experiment_by_name(experiment_name)
        
        if experiment:
            return experiment.experiment_id
        
        try:
            # Taggear el experimento para fácil filtrado
            tags = {"tenant_id": tenant_id, "project": "astra-learn"}
            return self.client.create_experiment(experiment_name, tags=tags)
        except Exception as e:
            logger.error(f"Error creando experimento para {tenant_id}: {e}")
            raise

    def start_training_run(self, tenant_id: str, run_name: str = None) -> mlflow.ActiveRun:
        """Inicia un contexto de ejecución para trackear métricas."""
        experiment_id = self.setup_tenant_experiment(tenant_id)
        return mlflow.start_run(
            experiment_id=experiment_id, 
            run_name=run_name or f"finetune_{tenant_id}"
        )

    def log_training_artifacts(self, model_path: str, artifact_path: str = "adapter_model"):
        """Sube los pesos del modelo (LoRA adapter) al registro."""
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model path {model_path} does not exist")
        
        mlflow.log_artifacts(model_path, artifact_path=artifact_path)
        logger.info(f"Artefactos subidos a {artifact_path}")

    def register_model_version(self, run_id: str, model_name: str, artifact_path: str = "adapter_model"):
        """Registra una versión oficial del modelo para despliegue."""
        model_uri = f"runs:/{run_id}/{artifact_path}"
        registered_model = mlflow.register_model(model_uri, model_name)
        return registered_model.version

    def get_latest_model_uri(self, model_name: str, stage: str = "Production") -> Optional[str]:
        """Recupera la URI del modelo para que ASTRA-CORE lo descargue."""
        try:
            models = self.client.get_latest_versions(model_name, stages=[stage])
            if models:
                return models[0].source
            return None
        except Exception as e:
            logger.warning(f"No se encontró modelo {model_name} en stage {stage}: {e}")
            return None
