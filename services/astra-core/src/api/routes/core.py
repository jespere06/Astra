from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import time
import json

from src.logic.intent_classifier import IntentClassifier
from src.nlp.cleaner import TextSanitizer
from src.config import get_settings, Settings
# Assuming models or logic from prev steps
try:
    from src.generated.astra_models_pb2 import IntentType
except ImportError:
    IntentType = str # Fallback

from src.inference.llm_engine import LLMEngine
from src.logic.enricher import EntityEnricher

router = APIRouter(prefix="/v1/core", tags=["Core Logic"])

class ProcessRequest(BaseModel):
    raw_text: str
    tenant_id: str
    stream: bool = False
    temperature: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = {}

class ProcessResponse(BaseModel):
    raw_text: str
    formal_text: Optional[str] = None
    clean_text: str
    intent: str
    template_id: Optional[str]
    confidence: float
    structured_data: Optional[List[Dict[str, Any]]]
    metadata: Dict[str, Any]
    processing_time_ms: float

# Instancia Singleton (junto con las otras)
classifier = IntentClassifier()
sanitizer = TextSanitizer()
enricher = EntityEnricher()
llm_engine = LLMEngine() # Lazy loads the model via ModelLoader

@router.post("/process", response_model=ProcessResponse)
async def process_text(
    request: ProcessRequest,
    settings: Settings = Depends(get_settings)
):
    start_time = time.time()
    
    # Override settings if request params provided
    if request.temperature:
        settings.TEMPERATURE = request.temperature

    # 1. LLM Generative Path (New)
    if settings.ENABLE_LLM_EXTRACTION:
        if request.stream:
            return StreamingResponse(
                llm_engine.generate_stream(request.raw_text),
                media_type="text/event-stream"
            )
        else:
            formal_text = llm_engine.generate(request.raw_text)
            duration = (time.time() - start_time) * 1000
            
            # Metadata for tracking
            meta = request.metadata or {}
            meta.update({
                "model": settings.MODEL_ID, 
                "adapter": settings.LORA_ADAPTER_PATH,
                "mode": "generative"
            })
            
            return {
                "raw_text": request.raw_text,
                "formal_text": formal_text,
                "clean_text": request.raw_text, # Same as raw in this mode
                "intent": "formalization",
                "template_id": "llm-v1",
                "confidence": 1.0,
                "structured_data": {},
                "metadata": meta,
                "processing_time_ms": duration
            }

    # 2. Legacy Rule-Based Path
    clean_text = sanitizer.clean(request.raw_text)
    entities_map = request.metadata.get("entities_dictionary", {})
    enriched_text = enricher.apply(clean_text, entities_map)
    
    classification_result = classifier.classify(enriched_text, request.tenant_id)
    
    duration = (time.time() - start_time) * 1000
    
    # Serialize Enum if needed
    intent_val = classification_result["intent"]
    if hasattr(intent_val, "value"):
        intent_val = intent_val.value

    return {
        "raw_text": request.raw_text,
        "clean_text": enriched_text,
        "intent": intent_val,
        "template_id": classification_result.get("template_id"),
        "confidence": classification_result.get("confidence", 0.0),
        "structured_data": classification_result.get("structured_data"),
        "metadata": classification_result.get("metadata", {}),
        "processing_time_ms": duration
    }
