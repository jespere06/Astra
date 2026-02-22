import logging
import torch
from typing import Dict, Any, Tuple
from datasets import load_dataset
from jiwer import wer
from transformers import PreTrainedTokenizer, PreTrainedModel
import mlflow

logger = logging.getLogger(__name__)

class ModelEvaluator:
    """
    Quality Gate para modelos entrenados.
    Ejecuta inferencia sobre un set de validación y decide si el modelo pasa a prod.
    """
    
    def __init__(self, model: PreTrainedModel, tokenizer: PreTrainedTokenizer):
        self.model = model
        self.tokenizer = tokenizer
        
    def evaluate(self, validation_dataset_uri: str, baseline_wer: float = 0.4) -> Tuple[bool, Dict[str, float]]:
        logger.info(f"Iniciando evaluación contra {validation_dataset_uri}...")
        
        # 1. Cargar Datos (Streaming para eficiencia)
        dataset = load_dataset("json", data_files=validation_dataset_uri, split="train")
        
        # Seleccionar muestra representativa si es muy grande
        if len(dataset) > 100:
            dataset = dataset.shuffle(seed=42).select(range(100))
        
        references = []
        predictions = []
        
        # 2. Inferencia (Batch size 1 para simplicidad en script)
        self.model.eval()
        
        # Detectar dispositivo
        device = next(self.model.parameters()).device
        
        for example in dataset:
            prompt = self._format_prompt(example)
            inputs = self.tokenizer(prompt, return_tensors="pt").to(device)
            
            with torch.no_grad():
                # Generar solo la respuesta (max 200 tokens nuevos)
                outputs = self.model.generate(
                    **inputs, 
                    max_new_tokens=200, 
                    pad_token_id=self.tokenizer.eos_token_id
                )
                
            decoded = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            # Extraer solo la parte de la respuesta (post prompt)
            response = decoded.split("### Response:")[-1].strip()
            
            predictions.append(response)
            references.append(example['output'])

        # 3. Cálculo de Métricas
        model_wer = wer(references, predictions)
        
        metrics = {
            "wer": model_wer,
            "baseline_wer": baseline_wer
        }
        
        # 4. Decisión (Quality Gate)
        # Permitimos una degradación mínima del 2% respecto al baseline (factor 1.02)
        # O un umbral absoluto si no hay baseline histórico confiable
        passed = model_wer <= (baseline_wer * 1.02)
        
        logger.info(f"Evaluación Finalizada. WER: {model_wer:.4f}. Passed: {passed}")
        
        # Reportar a MLflow
        mlflow.log_metrics(metrics)
        
        return passed, metrics

    def _format_prompt(self, example):
        # Mismo formato que en entrenamiento
        return f"### Instruction:\n{example['instruction']}\n\n### Input:\n{example['input']}\n\n### Response:\n"
