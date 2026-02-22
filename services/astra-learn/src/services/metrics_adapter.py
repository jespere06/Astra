import logging
import mlflow
from typing import Dict, Any, List, Optional
from src.config import settings

logger = logging.getLogger(__name__)

class MetricsAdapter:
    def __init__(self):
        mlflow.set_tracking_uri(settings.MLFLOW_URI)
        self.client = mlflow.tracking.MlflowClient()

    def get_job_details(self, run_id: str) -> Optional[Dict[str, Any]]:
        """
        Recupera métricas detalladas y parámetros de un Run de MLflow.
        """
        try:
            run = self.client.get_run(run_id)
            
            # Obtener historial de métricas para gráficas (ej. loss por step)
            try:
                loss_history = self.client.get_metric_history(run_id, "train/loss")
            except:
                loss_history = []
                
            try:
                eval_wer_history = self.client.get_metric_history(run_id, "eval/wer")
            except:
                eval_wer_history = []

            return {
                "params": run.data.params,
                "metrics": {
                    "final_loss": run.data.metrics.get("train/loss"),
                    "final_wer": run.data.metrics.get("eval/wer"),
                },
                "charts": {
                    "loss": [{"step": m.step, "value": m.value} for m in loss_history],
                    "wer": [{"step": m.step, "value": m.value} for m in eval_wer_history]
                },
                "artifacts_uri": run.info.artifact_uri
            }
        except Exception as e:
            logger.error(f"Error fetching MLflow metrics for run {run_id}: {e}")
            return None
