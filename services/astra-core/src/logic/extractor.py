import logging
from typing import List, Dict, Any, Optional
from src.config import get_settings

from .extraction.rules_based import RulesBasedStrategy
from .extraction.llm_few_shot import LLMFewShotStrategy

logger = logging.getLogger(__name__)

class DataExtractor:
    """
    Fachada principal para la extracción de datos estructurados.
    Implementa patrón Chain of Responsibility o Fallback.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.rules_strategy = RulesBasedStrategy()
        self.llm_strategy = LLMFewShotStrategy()

    async def extract_structured_data(
        self, 
        text: str, 
        schema_metadata: List[str], 
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Intenta extraer datos estructurados usando Reglas y luego LLM.
        
        Args:
            text: Texto limpio.
            schema_metadata: Lista de variables/columnas esperadas (vienen del Template).
            context: Contexto del request (incluye tenant_id, template_id).
        """
        if not text or not schema_metadata:
            return []

        # 1. Intento Determinista (Rápido, Gratis)
        try:
            data = await self.rules_strategy.extract(text, schema_metadata, context)
            if data:
                return data
        except Exception as e:
            logger.warning(f"Fallo en extracción por reglas: {e}")

        # 2. Intento Probabilístico (Lento, Costo) - Solo si está habilitado
        # Verificamos flag global o flag específico del request en context
        enable_llm = context.get("flags", {}).get("enable_llm_extraction", self.settings.ENABLE_LLM_EXTRACTION)
        
        if enable_llm:
            try:
                data = await self.llm_strategy.extract(text, schema_metadata, context)
                if data:
                    return data
            except Exception as e:
                logger.error(f"Fallo en extracción por LLM: {e}")

        # 3. Fallback final: No se pudo estructurar
        return []
