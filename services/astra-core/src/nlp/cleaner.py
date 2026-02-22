import re
import unicodedata
import logging
from typing import Optional
from .constants import CONTRACTIONS, FILLERS, BAD_CHARS

logger = logging.getLogger(__name__)

class TextSanitizer:
    """
    Motor de normalización lingüística para ASTRA-CORE.
    Elimina ruido del motor ASR y estandariza el texto para vectorización.
    """

    def __init__(self):
        logger.info("⚙️ Inicializando TextSanitizer y compilando Regex...")
        
        # 1. Regex para Contracciones (Compilación única para O(1) lookup)
        # Crea un patrón del tipo: \b(pa|pal|to)\b
        self._contractions_pattern = re.compile(
            r'\b(' + '|'.join(map(re.escape, CONTRACTIONS.keys())) + r')\b',
            re.IGNORECASE
        )

        # 2. Regex para Muletillas (Fillers)
        # Ordenamos por longitud descendente para atrapar frases largas primero ("o sea" antes que "o")
        sorted_fillers = sorted(FILLERS, key=len, reverse=True)
        self._fillers_pattern = re.compile(
            r'\b(' + '|'.join(map(re.escape, sorted_fillers)) + r')\b',
            re.IGNORECASE
        )

        # 3. Regex para espacios múltiples
        self._whitespace_pattern = re.compile(r'\s+')

        # 4. Regex para puntuación repetida (ej: "hola..." -> "hola.")
        self._dedup_punct_pattern = re.compile(r'([.,;?!])\1+')

    def _expand_match(self, match: re.Match) -> str:
        """Callback para reemplazar contracciones manteniendo casing básico."""
        word = match.group(0)
        lower_word = word.lower()
        replacement = CONTRACTIONS.get(lower_word, word)
        
        # Intentar preservar mayúsculas simples
        if word.isupper():
            return replacement.upper()
        if word[0].isupper():
            return replacement.capitalize()
        return replacement

    def clean(self, text: Optional[str]) -> str:
        """
        Ejecuta el pipeline completo de limpieza.
        Latencia esperada: < 5ms para textos de tamaño medio.
        """
        if not text or not isinstance(text, str):
            return ""

        # A. Normalización Unicode (NFC)
        # Evita problemas con tildes combinadas (e + ´ vs é)
        text = unicodedata.normalize('NFC', text)

        # B. Eliminación de caracteres basura/control
        for char in BAD_CHARS:
            text = text.replace(char, ' ')

        # C. Expansión de Contracciones (ej: "pa" -> "para")
        text = self._contractions_pattern.sub(self._expand_match, text)

        # D. Eliminación de Muletillas (ej: "eh", "mmm")
        text = self._fillers_pattern.sub('', text)

        # E. Deduplicación de puntuación (ej: "hola.." -> "hola.")
        text = self._dedup_punct_pattern.sub(r'\1', text)

        # F. Normalización de espacios (Trim y colapso)
        text = self._whitespace_pattern.sub(' ', text).strip()

        # G. Capitalización básica de sentencia (Si empieza con minúscula)
        if len(text) > 0 and text[0].islower():
            text = text[0].upper() + text[1:]

        return text
