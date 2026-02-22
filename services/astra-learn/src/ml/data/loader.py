import logging
import os
import boto3
from datasets import load_dataset, Dataset
from transformers import PreTrainedTokenizer
from trl import DataCollatorForCompletionOnlyLM

logger = logging.getLogger(__name__)

class DataLoader:
    """
    Gestiona la ingesta de datasets JSONL desde S3 y su preparación para SFT (Supervised Fine-Tuning).
    """
    def __init__(self, tokenizer: PreTrainedTokenizer):
        self.tokenizer = tokenizer
        self.s3 = boto3.client('s3')

    def load_from_s3(self, s3_uri: str, local_path: str = "/tmp/dataset.jsonl") -> Dataset:
        """Descarga y carga el dataset en formato HuggingFace."""
        try:
            bucket, key = s3_uri.replace("s3://", "").split("/", 1)
            logger.info(f"Descargando dataset desde {s3_uri}...")
            
            self.s3.download_file(bucket, key, local_path)
            
            dataset = load_dataset("json", data_files=local_path, split="train")
            logger.info(f"Cargados {len(dataset)} ejemplos.")
            return dataset
        except Exception as e:
            logger.error(f"Error cargando dataset desde S3: {e}")
            raise

    def format_prompt(self, example):
        """
        Convierte el par Input/Output al formato de Chat / Instruct.
        """
        # Formato Instruct Estándar para entrenamiento de alineación
        text = f"### Instruction:\n{example['instruction']}\n\n### Input:\n{example['input']}\n\n### Response:\n{example['output']}"
        return {"text": text}

    def get_data_collator(self):
        """
        Retorna un colador que ignora el loss de la instrucción.
        Esto asegura que el modelo aprenda a generar la respuesta, no a repetir el prompt.
        """
        response_template = "### Response:\n"
        return DataCollatorForCompletionOnlyLM(
            response_template=response_template, 
            tokenizer=self.tokenizer
        )
