import argparse
import logging
import os
import mlflow
from trl import SFTTrainer
from transformers import TrainingArguments

from src.ml.model_builder import ModelFactory
from src.ml.data.loader import DataLoader
from src.ml.callbacks import AstraCallback
from src.ml.evaluator import ModelEvaluator
from src.deployment.promoter import ModelPromoter
import time

# Configuración de Logging para entornos de entrenamiento (Verbose)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("ASTRA-TRAINER")

def parse_args():
    parser = argparse.ArgumentParser(description="ASTRA-LEARN: LoRA Fine-Tuning Engine")
    parser.add_argument("--tenant_id", type=str, required=True, help="ID del inquilino (aislamiento)")
    parser.add_argument("--dataset_uri", type=str, required=True, help="S3 URI del dataset .jsonl")
    parser.add_argument("--base_model", type=str, default="meta-llama/Llama-2-7b-hf", help="Modelo base de HF")
    parser.add_argument("--output_uri", type=str, required=True, help="S3 URI destino para el adaptador")
    parser.add_argument("--validation_set_uri", type=str, default=None, help="S3 URI del set de validación .jsonl")
    parser.add_argument("--epochs", type=int, default=3, help="Número de épocas de entrenamiento")
    parser.add_argument("--batch_size", type=int, default=4, help="Tamaño de batch por dispositivo")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning Rate")
    return parser.parse_args()

def main():
    args = parse_args()
    
    # 1. Configuración de Experimento en MLflow
    mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    mlflow.set_tracking_uri(mlflow_uri)
    mlflow.set_experiment(f"astra/tenant_{args.tenant_id}")
    
    with mlflow.start_run(run_name=f"finetune_{args.tenant_id}"):
        # Registrar hiperparámetros
        mlflow.log_params(vars(args))
        
        # 2. Factoría de Modelo: Carga Llama/Mistral con QLoRA
        factory = ModelFactory(args.base_model)
        model, tokenizer, peft_config = factory.load()
        
        # 3. Preparación de Datos: Streaming desde S3
        loader = DataLoader(tokenizer)
        raw_dataset = loader.load_from_s3(args.dataset_uri)
        # Aplicar mapeo de prompts Instruct
        formatted_dataset = raw_dataset.map(loader.format_prompt)
        
        # 4. Configuración del Trainer de HuggingFace
        training_args = TrainingArguments(
            output_dir="./results",
            num_train_epochs=args.epochs,
            per_device_train_batch_size=args.batch_size,
            gradient_accumulation_steps=4, # Aumenta el batch size efectivo
            learning_rate=args.lr,
            logging_steps=5,
            fp16=True,                # Entrenamiento en media precisión para velocidad
            optim="paged_adamw_8bit", # Optimización de VRAM agresiva
            lr_scheduler_type="cosine",
            warmup_ratio=0.03,
            save_strategy="no",       # Guardado manual al final por simplicidad en Jobs efímeros
            report_to="none"          # Desactivamos nativo para usar nuestro Callback custom
        )
        
        # 5. Inicialización del SFTTrainer (Supervised Fine-Tuning)
        trainer = SFTTrainer(
            model=model,
            train_dataset=formatted_dataset,
            peft_config=peft_config,
            dataset_text_field="text",
            max_seq_length=2048,
            tokenizer=tokenizer,
            args=training_args,
            data_collator=loader.get_data_collator(),
            callbacks=[AstraCallback(args.tenant_id, args.output_uri)]
        )
        
        # 6. Lanzamiento del Proceso de Entrenamiento
        logger.info(f"🚀 Iniciando entrenamiento LoRA para Tenant {args.tenant_id}...")
        trainer.train()
        
        # 7. Guardado Extra Local (El callback se encarga de subirlo a S3)
        trainer.model.save_pretrained("./results")
        
        # --- FASE 7: EVALUACIÓN Y PROMOCIÓN (NUEVO) ---
        if args.validation_set_uri:
            logger.info("Iniciando fase de Quality Gate...")
            
            # Instanciar evaluador con el modelo recién entrenado (aún en memoria)
            evaluator = ModelEvaluator(trainer.model, tokenizer)
            
            # Ejecutar evaluación
            passed, metrics = evaluator.evaluate(
                args.validation_set_uri, 
                baseline_wer=0.35 # Podría venir de args o DB
            )
            
            if passed:
                logger.info("✅ Quality Gate SUPERADO. Iniciando promoción...")
                
                # Reportar version a MLflow
                version_id = f"v_{int(time.time())}"
                mlflow.set_tag("model_version", version_id)
                mlflow.set_tag("quality_gate", "passed")
                
                # Promover modelo
                promoter = ModelPromoter()
                promoter.promote(args.tenant_id, args.output_uri, version_id)
                
            else:
                logger.warning(f"⛔ Quality Gate FALLIDO (WER: {metrics['wer']}). Modelo no promovido.")
                mlflow.set_tag("quality_gate", "failed")
        
        logger.info("✅ Pipeline de entrenamiento y evaluación finalizado.")

if __name__ == "__main__":
    main()
