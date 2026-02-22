import torch
import logging
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

logger = logging.getLogger(__name__)

class ModelFactory:
    """
    Configura y carga modelos LLM con técnicas de QLoRA para eficiencia de VRAM.
    """
    def __init__(self, model_id: str):
        self.model_id = model_id
        
        # Configuración de Cuantización (4-bit NF4) para GPUs con VRAM limitada
        self.bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True
        )

        # Configuración LoRA (Low-Rank Adaptation)
        self.peft_config = LoraConfig(
            r=16,               # Rank
            lora_alpha=32,      # Scaling factor
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            # Apuntar a todas las capas lineales para máxima capacidad de aprendizaje
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"] 
        )

    def load(self):
        logger.info(f"Cargando modelo y tokenizer base: {self.model_id}...")
        
        tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        # Asegurar token de padding coherente
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token
        tokenizer.padding_side = "right" # Recomendado para entrenamiento FP16

        model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            quantization_config=self.bnb_config,
            device_map="auto",
            trust_remote_code=True
        )

        # Preparar modelo para entrenamiento con pesos cuantizados
        model = prepare_model_for_kbit_training(model)
        
        # Inyectar adaptadores LoRA
        model = get_peft_model(model, self.peft_config)
        
        # Imprimir resumen de parámetros (útil para auditoría de recursos)
        trainable_params, all_param = model.get_nb_trainable_parameters()
        logger.info(
            f"Parámetros entrenables: {trainable_params:,d} || "
            f"Total: {all_param:,d} || "
            f"Ratio: {100 * trainable_params / all_param:.4f}%"
        )

        return model, tokenizer, self.peft_config
