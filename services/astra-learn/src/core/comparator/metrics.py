import logging
from typing import Dict
import numpy as np
from jiwer import wer
from rapidfuzz import fuzz

# Carga perezosa de BERTScore para no bloquear inicio si no hay GPU/Recursos
try:
    from bert_score import score as bert_score
    import torch
    BERT_AVAILABLE = torch.cuda.is_available() or torch.backends.mps.is_available() or True 
except ImportError:
    bert_score = None
    BERT_AVAILABLE = False

logger = logging.getLogger(__name__)

class MetricsEngine:
    
    @staticmethod
    def calculate_wer(reference: str, hypothesis: str) -> float:
        """
        Calcula Word Error Rate.
        0.0 = Perfecto match.
        > 1.0 = Totalmente diferente.
        """
        if not reference and not hypothesis:
            return 0.0
        if not reference:
            return 1.0
            
        try:
            return float(wer(reference, hypothesis))
        except Exception as e:
            logger.error(f"Error calculando WER: {e}")
            return 1.0

    @staticmethod
    def calculate_semantic_similarity(reference: str, hypothesis: str) -> float:
        """
        Calcula similitud semántica.
        Usa BERTScore si está disponible, sino fallback a Levenshtein (RapidFuzz).
        Retorna 0.0 (diferente) a 1.0 (igual).
        """
        if not reference or not hypothesis:
            return 0.0

        # Fast Path: Identicos
        if reference.strip() == hypothesis.strip():
            return 1.0

        # Si BERTScore está disponible, lo usamos para entender el significado
        if BERT_AVAILABLE and bert_score is not None:
            try:
                # BERTScore retorna (P, R, F1)
                _, _, f1 = bert_score([hypothesis], [reference], lang="es", verbose=False)
                return float(f1.item())
            except Exception as e:
                logger.warning(f"Fallo BERTScore, usando fallback: {e}")

        # Fallback (CPU Friendly)
        # Token Sort Ratio maneja palabras desordenadas mejor que ratio simple
        return float(fuzz.token_sort_ratio(reference, hypothesis) / 100.0)

    @staticmethod
    def classify_change(wer_score: float, sim_score: float) -> str:
        """Determina el tipo de cambio para etiquetado."""
        if wer_score == 0.0:
            return "NO_CHANGE"
        
        if wer_score < 0.05:
            return "FIX_ORTHOGRAPHY" # Cambios mínimos (puntos, tildes)
            
        if wer_score < 0.2 and sim_score > 0.95:
            return "MINOR_EDIT"
            
        if sim_score > 0.85:
            return "REPHRASE"   # Mismo significado, vocabulario diferente
            
        if sim_score < 0.4:
            return "MAJOR_REWRITE" # Cambio radical de contenido
            
        return "CONTENT_UPDATE" # Ajuste de información
