import re
import logging
import spacy
from typing import List, Optional

logger = logging.getLogger(__name__)

class TextSanitizer:
    """
    Motor de pre-procesamiento lingüístico.
    Se encarga de limpiar ruido y anonimizar entidades (PII) antes de la vectorización.
    """

    # Mapeo de entidades de Spacy a Tokens genéricos de ASTRA
    ENTITY_MAP = {
        "PER": "{PERSONA}",
        "LOC": "{LUGAR}",
        "ORG": "{ORG}",
        "DATE": "{FECHA}",
        # "MISC": "{MISC}" # Generalmente ruidoso, lo ignoramos por defecto
    }

    def __init__(self, model_size: str = "lg"):
        self.nlp = self._load_spacy_model(model_size)
        
        # Regex pre-compilados para rendimiento
        self.regex_spaces = re.compile(r'\s+')
        self.regex_control = re.compile(r'[\x00-\x1f\x7f-\x9f]')
        # Normalización de comillas tipográficas a estándar
        self.regex_quotes = re.compile(r'[“”«»]')

    def _load_spacy_model(self, size: str):
        """Carga el modelo Spacy optimizado para inferencia (sin entrenamiento)."""
        model_name = f"es_core_news_{size}"
        try:
            logger.info(f"Cargando modelo NER: {model_name}...")
            # Desactivamos componentes que no necesitamos para NER para ganar velocidad
            nlp = spacy.load(model_name, disable=["tagger", "parser", "attribute_ruler", "lemmatizer"])
            return nlp
        except OSError:
            logger.warning(f"Modelo {model_name} no encontrado. Intentando fallback a 'sm'...")
            try:
                # Fallback para entornos de desarrollo sin el modelo grande
                return spacy.load("es_core_news_sm", disable=["tagger", "parser", "attribute_ruler", "lemmatizer"])
            except OSError:
                logger.error("No se encontraron modelos de Spacy. La anonimización NER estará desactivada.")
                return None

    def _clean_regex(self, text: str) -> str:
        """Limpieza determinística básica."""
        if not text:
            return ""
        
        # 1. Eliminar caracteres de control
        text = self.regex_control.sub('', text)
        
        # 2. Normalizar comillas
        text = self.regex_quotes.sub('"', text)
        
        # 3. Colapsar espacios múltiples y saltos de línea
        text = self.regex_spaces.sub(' ', text)
        
        return text.strip()

    def _anonymize_ner(self, text: str) -> str:
        """Reemplaza entidades nombradas por tokens genéricos usando Spacy."""
        if not self.nlp:
            return text

        doc = self.nlp(text)
        
        # Creamos una lista de reemplazos.
        # Es crítico iterar en reverso para no alterar los índices de caracteres
        # de entidades que aparecen antes en el string.
        replacements = []
        
        for ent in doc.ents:
            if ent.label_ in self.ENTITY_MAP:
                token = self.ENTITY_MAP[ent.label_]
                replacements.append((ent.start_char, ent.end_char, token))
        
        # Ordenar por posición descendente (de fin a inicio)
        replacements.sort(key=lambda x: x[0], reverse=True)
        
        # Aplicar reemplazos
        text_list = list(text)
        for start, end, token in replacements:
            text_list[start:end] = list(token)
            
        return "".join(text_list)

    def sanitize(self, text: str, anonymize: bool = True) -> str:
        """
        Ejecuta el pipeline completo de limpieza.
        
        Args:
            text: Texto crudo.
            anonymize: Si es True, aplica NER para ocultar nombres/fechas.
            
        Returns:
            Texto limpio y (opcionalmente) anonimizado.
        """
        if not text:
            return ""

        # 1. Limpieza estructural (rápida)
        clean_text = self._clean_regex(text)
        
        # 2. Anonimización (lenta, solo si se requiere)
        if anonymize and self.nlp:
            clean_text = self._anonymize_ner(clean_text)
            
        return clean_text