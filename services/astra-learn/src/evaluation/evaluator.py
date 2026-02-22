import logging
import json
import torch
import os
from typing import Dict, Any, List
from datasets import load_dataset
from .metrics import MetricsEngine

# Manejo de dependencias opcionales (unsloth)
try:
    from unsloth import FastLanguageModel
except ImportError:
    FastLanguageModel = None

import boto3

logger = logging.getLogger(__name__)

class EvalResult:
    def __init__(self, status: str, metrics: Dict[str, float], reasons: List[str], report_path: str):
        self.status = status
        self.metrics = metrics
        self.reasons = reasons
        self.report_path = report_path

    def to_dict(self):
        return {
            "status": self.status,
            "metrics": self.metrics,
            "reasons": self.reasons,
            "report_path": self.report_path
        }

class ModelEvaluator:
    """
    Juez automático que decide si un modelo candidato es apto para producción.
    """
    
    def __init__(self, base_model_id: str = "unsloth/llama-3-8b-Instruct-bnb-4bit", max_seq_length: int = 2048):
        self.metrics_engine = MetricsEngine()
        self.base_model_id = base_model_id
        self.max_seq_length = max_seq_length
        self.s3_client = boto3.client("s3")

    def _load_model(self, adapter_path: str):
        """Carga el modelo en modo inferencia 4-bit."""
        if FastLanguageModel is None:
            raise RuntimeError("Unsloth no está instalado. No se puede cargar el modelo para evaluación.")

        logger.info(f"Cargando adaptador para evaluación: {adapter_path}")
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=adapter_path, # Carga LoRA sobre el base model automáticamente
            max_seq_length=self.max_seq_length,
            dtype=None,
            load_in_4bit=True,
        )
        FastLanguageModel.for_inference(model)
        return model, tokenizer

    def evaluate(self, 
                 adapter_path: str, 
                 val_dataset_path: str, 
                 baseline_metrics: Dict[str, float],
                 tenant_id: str,
                 job_id: str) -> EvalResult:
        
        logger.info("🚀 Iniciando Evaluación de Calidad (The Judge)...")

        # 1. Cargar Datos
        try:
            dataset = load_dataset("json", data_files=val_dataset_path, split="train")
        except Exception as e:
            logger.error(f"Fallo cargando dataset de validación: {e}")
            return self._reject_fast("DATASET_ERROR", str(e))

        # Sampling si es muy grande (> 50 muestras para no demorar el worker)
        if len(dataset) > 50:
            dataset = dataset.shuffle(seed=42).select(range(50))

        # 2. Inferencia
        model, tokenizer = self._load_model(adapter_path)
        
        references = []
        predictions = []
        xml_valid_count = 0
        
        alpaca_prompt = """### Instruction:
{}

### Input:
{}

### Response:
"""
        
        for row in dataset:
            prompt = alpaca_prompt.format(row["instruction"], row["input"], "")
            inputs = tokenizer([prompt], return_tensors="pt").to("cuda")

            with torch.no_grad():
                outputs = model.generate(
                    **inputs, 
                    max_new_tokens=512, 
                    use_cache=True,
                    pad_token_id=tokenizer.eos_token_id
                )
            
            # Decodificar solo la respuesta nueva
            # Unsloth/Transformers devuelve todo el prompt + respuesta
            decoded = tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
            response = decoded.split("### Response:\n")[-1].strip()
            
            predictions.append(response)
            references.append(row["output"])
            
            if self.metrics_engine.validate_xml_structure(response):
                xml_valid_count += 1

        # 3. Cálculo de Métricas
        avg_wer = self.metrics_engine.calculate_wer(references, predictions)
        avg_sim = self.metrics_engine.calculate_semantic_similarity(references, predictions)
        xml_valid_ratio = xml_valid_count / len(dataset)
        
        current_metrics = {
            "wer": avg_wer,
            "semantic_similarity": avg_sim,
            "xml_valid_ratio": xml_valid_ratio
        }

        # 4. Decisión (Quality Gate)
        status = "REJECTED"
        reasons = []

        # Regla A: XML debe ser sólido (tolerancia mínima 95% para casos edge, ideal 100%)
        if xml_valid_ratio < 0.95:
            reasons.append(f"Fallo estructural crítico: XML válido solo {xml_valid_ratio:.2%}")

        # Regla B: No regresión severa en WER (permitir 5% de margen si mejora semántica)
        baseline_wer = baseline_metrics.get("wer", 1.0)
        if avg_wer > (baseline_wer * 1.05) and avg_wer > 0.1:
            reasons.append(f"Regresión WER detectada: {avg_wer:.4f} > {baseline_wer:.4f}")

        # Regla C: Similitud mínima
        if avg_sim < 0.7:
            reasons.append(f"Alucinación semántica: Similitud muy baja ({avg_sim:.2f})")

        if not reasons:
            status = "PROMOTED"

        # 5. Persistencia del Reporte
        report_key = f"reports/{tenant_id}/{job_id}/eval_report.json"
        report_body = {
            "job_id": job_id,
            "tenant_id": tenant_id,
            "decision": status,
            "metrics": current_metrics,
            "baseline": baseline_metrics,
            "reasons": reasons,
            "sample_size": len(dataset),
            "samples": [
                {"input": dataset[0]["input"][:100], "pred": predictions[0][:100], "ref": references[0][:100]}
            ] if len(dataset) > 0 else []
        }

        # Subir a S3 (Bucket de modelos definido en config o pasado por params)
        # Asumimos bucket 'astra-models' o similar configurado en entorno
        bucket_name = os.getenv("S3_MODELS_BUCKET", "astra-models")
        try:
            self.s3_client.put_object(
                Bucket=bucket_name,
                Key=report_key,
                Body=json.dumps(report_body, indent=2),
                ContentType="application/json"
            )
        except Exception as e:
            logger.error(f"No se pudo subir reporte a S3: {e}")
            report_key = "local_only"

        logger.info(f"Evaluación Finalizada: {status}. Métricas: {current_metrics}")
        return EvalResult(status, current_metrics, reasons, f"s3://{bucket_name}/{report_key}")

    def _reject_fast(self, reason_code, details):
        return EvalResult("REJECTED", {}, [f"{reason_code}: {details}"], "")