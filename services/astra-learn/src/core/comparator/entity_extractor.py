import logging
import spacy
from typing import Dict, List, Tuple
# Note: Since the previous code used .metrics, I'll follow that if it's in the same package
# but it was src/core/comparator/metrics.py, and this file is in same dir.

logger = logging.getLogger(__name__)

class HotfixDetector:
    """
    Motor de detección de correcciones rápidas.
    Identifica si un cambio en el texto corresponde únicamente a una corrección de entidad (Nombre/Lugar).
    """

    def __init__(self):
        # Usamos el modelo grande para máxima precisión en NER
        try:
            self.nlp = spacy.load("es_core_news_md")
        except OSError:
            logger.warning("Modelo Spacy no encontrado. Hotfix detector desactivado.")
            self.nlp = None

    def detect_hotfixes(self, delta_report: Dict) -> Dict[str, str]:
        """
        Analiza un reporte de deltas y extrae pares {error: corrección} para el diccionario.
        """
        hotfixes = {}
        
        if not self.nlp:
            return hotfixes

        for delta in delta_report.get("deltas", []):
            # Solo analizamos ediciones menores (MINOR_EDIT) o cambios ortográficos
            classification = delta.get("metrics", {}).get("classification")
            if classification not in ["MINOR_EDIT", "FIX_ORTHOGRAPHY"]:
                continue

            original = delta.get("original_text", "")
            final = delta.get("final_text", "")

            if not original or not final:
                continue

            # Análisis token por token (simplificado para MVP)
            candidate = self._analyze_pair(original, final)
            if candidate:
                err_term, fix_term = candidate
                # Normalización: Las llaves del dict siempre en minúsculas para búsqueda
                hotfixes[err_term.lower()] = fix_term

        if hotfixes:
            logger.info(f"Detectados {len(hotfixes)} hotfixes de entidades.")
            
        return hotfixes

    def _analyze_pair(self, original: str, final: str) -> Tuple[str, str]:
        """
        Compara dos frases cortas. Si la única diferencia es una entidad, retorna el par.
        """
        # Tokenización básica
        tokens_orig = original.split()
        tokens_final = final.split()

        # Solo soportamos cambios 1-a-1 por ahora para seguridad
        if len(tokens_orig) != len(tokens_final):
            return None

        diffs = []
        for o_tok, f_tok in zip(tokens_orig, tokens_final):
            if o_tok != f_tok:
                # Limpiar puntuación para comparar
                o_clean = o_tok.strip(".,;:()")
                f_clean = f_tok.strip(".,;:()")
                if o_clean != f_clean:
                    diffs.append((o_clean, f_clean))

        # Si hay exactamente 1 diferencia, analizamos si es entidad
        if len(diffs) == 1:
            err, fix = diffs[0]
            
            # Validar con NER: El término corregido debe ser una entidad válida
            doc = self.nlp(fix)
            if doc.ents and doc.ents[0].label_ in ["PER", "LOC", "ORG"]:
                # Filtro adicional: No aceptar si son verbos o stop words
                if not doc[0].is_stop and doc[0].pos_ != "VERB":
                    return (err, fix)
        
        return None
