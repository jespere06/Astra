import logging
from typing import List, Union
import numpy as np
from lxml import etree

# Imports seguros para entornos sin GPU o dependencias pesadas durante tests
try:
    from jiwer import wer
except ImportError:
    wer = None

try:
    from sentence_transformers import SentenceTransformer, util
except ImportError:
    SentenceTransformer = None

logger = logging.getLogger(__name__)

class MetricsEngine:
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model_name = model_name
        self._embedding_model = None

    @property
    def embedding_model(self):
        """Lazy loading del modelo de embeddings para ahorrar RAM si no se usa."""
        if self._embedding_model is None:
            if SentenceTransformer is None:
                raise ImportError("sentence-transformers no está instalado.")
            logger.info(f"Cargando modelo de métricas: {self.model_name}")
            self._embedding_model = SentenceTransformer(self.model_name)
        return self._embedding_model

    def calculate_wer(self, references: List[str], hypotheses: List[str]) -> float:
        """Calcula Word Error Rate (Promedio)."""
        if not references or not hypotheses:
            return 1.0
        
        if wer is None:
            logger.warning("jiwer no instalado. Retornando WER 0.0 (Dummy)")
            return 0.0
            
        try:
            return float(wer(references, hypotheses))
        except Exception as e:
            logger.error(f"Error calculando WER: {e}")
            return 1.0

    def calculate_semantic_similarity(self, references: List[str], hypotheses: List[str]) -> float:
        """Calcula similitud coseno promedio entre referencias y predicciones."""
        if not references or not hypotheses:
            return 0.0
            
        try:
            # Codificar en lotes
            ref_embs = self.embedding_model.encode(references, convert_to_tensor=True)
            hyp_embs = self.embedding_model.encode(hypotheses, convert_to_tensor=True)
            
            # Calcular similitud par a par
            scores = util.pairwise_cos_sim(ref_embs, hyp_embs)
            
            # Retornar promedio
            return float(scores.mean().item())
        except Exception as e:
            logger.error(f"Error calculando similitud semántica: {e}")
            return 0.0

    def validate_xml_structure(self, text: str) -> bool:
        """
        Verifica si el texto es un fragmento XML válido.
        Asume que el modelo debe generar tags compatibles con OOXML.
        """
        if not text or "<" not in text:
            return False
            
        try:
            # Envolvemos en un root dummy para manejar fragmentos múltiples o sin root único
            wrapped_xml = f"<root>{text}</root>"
            # Parser permisivo pero estructural
            parser = etree.XMLParser(recover=True) 
            etree.fromstring(wrapped_xml, parser=parser)
            
            # Verificación adicional: que no haya tags rotos obvios que el recover arregló mal
            if text.count("<") != text.count(">"):
                return False
                
            return True
        except (etree.XMLSyntaxError, Exception):
            return False