import torch
import logging

# Set up logger
logger = logging.getLogger(__name__)

# Envolver imports opcionales
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel
except ImportError:
    logger.warning("Transformers/PEFT not installed. LLM features will be unavailable.")
    AutoTokenizer = None
    AutoModelForCausalLM = None
    BitsAndBytesConfig = None
    PeftModel = None

from src.config import get_settings

settings = get_settings()

class ModelLoader:
    _instance = None
    model = None
    tokenizer = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ModelLoader, cls).__new__(cls)
            # Solo cargar si está habilitado en config
            if settings.ENABLE_LLM_EXTRACTION:
                cls._instance.load_model()
            else:
                logger.info("[ModelLoader] LLM Extraction disabled via config. Skipping load.")
        return cls._instance

    def load_model(self):
        """
        Loads the Quantized Base Model and attaches the LoRA Adapter.
        """
        if self.model is not None:
            return

        if not settings.ENABLE_LLM_EXTRACTION:
            return

        # Verificar si hay GPU NVIDIA disponible para 4-bit (bitsandbytes)
        if not torch.cuda.is_available():
            logger.warning("⚠️ [ModelLoader] CUDA not detected. 4-bit quantization (bitsandbytes) requires NVIDIA GPU.")
            logger.warning("⚠️ [ModelLoader] Skipping model load to prevent crash on Mac/CPU.")
            return

        if AutoModelForCausalLM is None:
            logger.error("❌ [ModelLoader] Transformers/PEFT not installed. Cannot load model.")
            return

        logger.info(f"[ModelLoader] Loading base model: {settings.MODEL_ID}...")
        
        try:
            # 1. 4-bit Quantization Config
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16
            )

            # 2. Load Base Model
            base_model = AutoModelForCausalLM.from_pretrained(
                settings.MODEL_ID,
                quantization_config=bnb_config,
                device_map="auto",
                trust_remote_code=True
            )
            
            # 3. Load Tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(
                settings.MODEL_ID,
                trust_remote_code=True
            )
            self.tokenizer.pad_token = self.tokenizer.eos_token

            # 4. Attach LoRA Adapter
            logger.info(f"[ModelLoader] Loading adapter from: {settings.LORA_ADAPTER_PATH}...")
            self.model = PeftModel.from_pretrained(
                base_model,
                settings.LORA_ADAPTER_PATH
            )
            
            # Switch to eval mode
            self.model.eval()
            logger.info("[ModelLoader] Model loaded successfully.")
            
        except Exception as e:
            # Capturamos el error pero NO relanzamos para que el servidor siga vivo
            logger.error(f"❌ [ModelLoader] CRITICAL ERROR: Failed to load model. {e}")
            logger.info("   -> Continuing without LLM capabilities.")
            self.model = None

    def get_model(self):
        return self.model

    def get_tokenizer(self):
        return self.tokenizer
