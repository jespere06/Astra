import json
import logging
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI
from src.config import get_settings
from .base import ExtractionStrategy

logger = logging.getLogger(__name__)

class LLMFewShotStrategy(ExtractionStrategy):
    """
    Motor probabilístico usando LLMs para estructurar texto complejo.
    """
    def __init__(self):
        self.settings = get_settings()
        self.client = AsyncOpenAI(api_key=self.settings.LLM_API_KEY or self.settings.OPENAI_API_KEY)
        self.model = self.settings.LLM_MODEL_NAME

    def _build_prompt(self, text: str, schema: List[str]) -> List[Dict]:
        columns_str = ", ".join(schema)
        
        system_msg = f"""
        Eres un asistente administrativo experto en actas.
        Tu tarea es extraer información del texto proporcionado y formatearla como un arreglo JSON de objetos.
        
        REGLAS:
        1. Solo extrae información que corresponda a las columnas: [{columns_str}].
        2. Si un dato no está explícito, usa null o cadena vacía.
        3. Normaliza los valores (ej: "sí", "afirmativo" -> "SÍ").
        4. Retorna SOLO un objeto JSON con la clave "data" que contiene la lista.
        5. Si no hay datos relevantes, retorna "data": [].
        """

        user_msg = f"Texto a procesar: \"{text}\""

        return [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_msg}
        ]

    async def extract(self, text: str, schema: List[str], context: Optional[Dict] = None) -> List[Dict[str, Any]]:
        self.settings = get_settings() # Reload settings in case they change or just to be safe
        
        if not self.settings.ENABLE_LLM_EXTRACTION:
            # Check context override
            if not context or not context.get("flags", {}).get("enable_llm_extraction", False):
                return []

        try:
            messages = self._build_prompt(text, schema)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1, # Determinismo alto
                max_tokens=500
            )

            content = response.choices[0].message.content
            parsed = json.loads(content)
            
            data = parsed.get("data", [])
            
            if data:
                logger.info(f"LLMStrategy: Extraídas {len(data)} filas vía IA.")
                
            return data

        except Exception as e:
            logger.error(f"LLMStrategy Error: {e}")
            return []
