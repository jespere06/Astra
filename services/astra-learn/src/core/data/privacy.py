import logging
from typing import Tuple, List, Dict
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

logger = logging.getLogger(__name__)

class PrivacyEngine:
    """
    Wrapper de Microsoft Presidio con soporte para español y consistencia de entidades.
    """
    
    def __init__(self, language: str = "es"):
        self.language = language
        # Inicializa el motor de análisis (carga modelos Spacy por debajo)
        try:
            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
            logger.info(f"PrivacyEngine inicializado en idioma: {language}")
        except Exception as e:
            logger.error(f"Error inicializando Presidio (¿Falta descargar spacy model?): {e}")
            raise e

    def _get_consistent_operators(self) -> Dict[str, OperatorConfig]:
        """Define cómo se reemplazan las entidades."""
        return {
            "PERSON": OperatorConfig("replace", {"new_value": "<PERSONA>"}),
            "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "<TELEFONO>"}),
            "EMAIL_ADDRESS": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
            "Credit_Card": OperatorConfig("replace", {"new_value": "<TARJETA>"}),
            "CRYPTO": OperatorConfig("replace", {"new_value": "<HASH>"}),
            "LOCATION": OperatorConfig("replace", {"new_value": "<LUGAR>"}),
        }

    def sanitize_pair(self, original_text: str, corrected_text: str) -> Tuple[str, str]:
        """
        Sanitiza un par de textos (Input/Output) manteniendo consistencia.
        """
        if not original_text or not corrected_text:
            return original_text, corrected_text

        DELIMITER = " |||SPLIT_MARKER||| "
        combined_text = f"{original_text}{DELIMITER}{corrected_text}"

        try:
            # 1. Análisis
            results = self.analyzer.analyze(
                text=combined_text,
                language=self.language,
                entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "LOCATION"]
            )

            # 2. Anonimización
            anonymized_result = self.anonymizer.anonymize(
                text=combined_text,
                analyzer_results=results,
                operators=self._get_consistent_operators()
            )
            
            sanitized_combined = anonymized_result.text

            # 3. Separación
            parts = sanitized_combined.split(DELIMITER)
            if len(parts) == 2:
                return parts[0].strip(), parts[1].strip()
            
            # Fallback
            logger.warning("Delimitador de sanitización perdido. Retornando sanitización individual.")
            return self._sanitize_single(original_text), self._sanitize_single(corrected_text)

        except Exception as e:
            logger.error(f"Fallo en sanitización: {e}")
            return "<ERROR_PRIVACY>", "<ERROR_PRIVACY>"

    def _sanitize_single(self, text: str) -> str:
        results = self.analyzer.analyze(text=text, language=self.language)
        return self.anonymizer.anonymize(text=text, analyzer_results=results, operators=self._get_consistent_operators()).text
