import os
import boto3
import logging
from transformers import TrainerCallback, TrainingArguments, TrainerState, TrainerControl
import mlflow

logger = logging.getLogger(__name__)

class AstraCallback(TrainerCallback):
    """
    Orquestador de eventos para integrar el entrenamiento con MLflow y S3.
    """
    def __init__(self, tenant_id: str, output_s3_uri: str):
        self.tenant_id = tenant_id
        self.output_s3_uri = output_s3_uri
        self.s3 = boto3.client('s3')

    def on_log(self, args: TrainingArguments, state: TrainerState, control: TrainerControl, logs=None, **kwargs):
        """Enlaza logs del Trainer directamente con MLflow."""
        if logs:
            # Filtrar métricas numéricas para evitar errores de tipo en MLflow
            metrics = {k: v for k, v in logs.items() if isinstance(v, (int, float, complex))}
            mlflow.log_metrics(metrics, step=state.global_step)

    def on_train_end(self, args: TrainingArguments, state: TrainerState, control: TrainerControl, **kwargs):
        """Al finalizar las épocas, empaqueta el adaptador LoRA y lo sube al Vault de S3."""
        logger.info("Entrenamiento finalizado. Iniciando exportación de artefactos a S3...")
        
        local_dir = args.output_dir # Generalmente "./results"
        
        try:
            bucket, prefix = self._parse_s3_uri(self.output_s3_uri)
            
            # Recorrido recursivo para subir todos los archivos del adaptador (bin, config, tokenizer)
            for root, _, files in os.walk(local_dir):
                for file in files:
                    local_path = os.path.join(root, file)
                    # Mantener estructura de directorios si existiera
                    rel_path = os.path.relpath(local_path, local_dir)
                    s3_key = os.path.join(prefix, rel_path)
                    
                    logger.info(f"Subiendo artefacto: {file} -> s3://{bucket}/{s3_key}")
                    self.s3.upload_file(local_path, bucket, s3_key)
            
            logger.info(f"✅ Adaptador persistido exitosamente en {self.output_s3_uri}")
            
        except Exception as e:
            logger.error(f"Fallo crítico subiendo artefactos a S3: {e}")

    def _parse_s3_uri(self, uri: str):
        parts = uri.replace("s3://", "").split("/", 1)
        if len(parts) < 2:
            raise ValueError(f"S3 URI inválida: {uri}")
        return parts[0], parts[1]
