import time
import logging
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List

from src.schemas.process import ProcessingRequest, AstraBlockResponse
from src.generated.astra_models_pb2 import IntentType

from src.logic.scheduler import governor
from src.schemas.qos_models import TaskPriority

from src.nlp.cleaner import TextSanitizer
from src.logic.intent_classifier import IntentClassifier
from src.logic.enricher import EntityEnricher
from src.config import get_settings
from src.logic.extractor import DataExtractor

logger = logging.getLogger(__name__)

class SemanticPipeline:
    def __init__(self):
        settings = get_settings()
        logger.info("🔧 Inicializando Pipeline Semántico")
        
        self.sanitizer = TextSanitizer()
        self.classifier = IntentClassifier()
        self.enricher = EntityEnricher()
        self.extractor = DataExtractor()

    async def execute(self, request: ProcessingRequest) -> AstraBlockResponse:
        start_time = time.time()
        warnings: List[str] = []
        
        # 1. Obtención de Texto (ASR o Directo)
        raw_text = ""
        provider = request.flags.get("provider", "deepgram")

        if request.text_content:
            raw_text = request.text_content
        elif request.audio_content:
            # Usar el gobernador central (soporta Deepgram/Whisper)
            asr_result = await governor.process_request(
                audio=request.audio_content,
                priority=TaskPriority.LIVE_SESSION,
                tenant_id=request.tenant_id,
                provider=provider
            )

            if asr_result.status == "audio_pending" or asr_result.status == "failed":
                raise Exception(f"ASR_CRITICAL_FAILURE: {asr_result.qos_meta.error_details}")
            
            raw_text = asr_result.text
            if asr_result.qos_meta.failover_occurred:
                warnings.append(f"ASR Failover: {asr_result.qos_meta.error_details}")
        else:
            raise ValueError("Payload vacío: Se requiere audio o texto.")

        # 2. Sanitización
        try:
            clean_text = self.sanitizer.clean(raw_text)
        except Exception as e:
            logger.error(f"Error en Sanitizer: {e}")
            clean_text = raw_text
            warnings.append("Sanitizer skipped due to error")

        # 3. Clasificación
        intent_result = {
            "intent": IntentType.INTENT_FREE_TEXT,
            "template_id": "",
            "confidence": 0.0,
            "structured_data": None,
            "metadata": {}
        }
        
        try:
            intent_result = self.classifier.classify(clean_text, request.tenant_id)
        except Exception as e:
            logger.error(f"Error en Classifier: {e}")
            warnings.append("Classifier skipped due to error")
        
        intent_type = intent_result.get("intent", IntentType.INTENT_FREE_TEXT)
        variables = intent_result.get("metadata", {}).get("variables", [])

        # 4. Enriquecimiento de Entidades (Hotfix)
        final_text = clean_text
        try:
            if request.entities_dictionary:
                final_text = self.enricher.apply(clean_text, request.entities_dictionary)
        except Exception as e:
            logger.error(f"Error en Enricher: {e}")
            warnings.append("Enricher skipped due to error")

        # 4.5 Extracción de Datos Estructurados
        structured_data = intent_result.get("structured_data")
        
        if not structured_data:
             if intent_type in [IntentType.INTENT_TEMPLATE, IntentType.INTENT_HYBRID] and variables:
                try:
                    extraction_context = {
                        "tenant_id": request.tenant_id,
                        "template_id": intent_result.get("template_id"),
                        "flags": request.flags
                    }
                    
                    structured_data = await self.extractor.extract_structured_data(
                        text=clean_text,
                        schema_metadata=variables,
                        context=extraction_context
                    )
                except Exception as e:
                    logger.error(f"Error en Extractor: {e}")
                    warnings.append("Extractor skipped due to error")

        # 5. Construcción de Respuesta
        duration = (time.time() - start_time) * 1000
        
        try:
            tz = ZoneInfo(request.client_timezone)
        except:
            tz = ZoneInfo("UTC")
            
        local_now = datetime.now(tz).isoformat()

        intent_val = intent_type
        if hasattr(intent_val, "value"):
             intent_val = intent_val.value

        return AstraBlockResponse(
            raw_text=raw_text,
            clean_text=final_text,
            intent=intent_val,
            template_id=intent_result["template_id"],
            confidence=intent_result["confidence"],
            structured_data=structured_data,
            metadata=intent_result["metadata"],
            processed_at=local_now,
            processing_time_ms=duration,
            warnings=warnings
        )