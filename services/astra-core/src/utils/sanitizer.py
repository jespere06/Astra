import re

class TextSanitizer:
    # Lista básica de muletillas en español coloquial administrativo
    FILLERS = [
        r"\beh\b", r"\bmmm\b", r"\beste\b", r"\buuh\b", r"\bpues\b"
    ]
    
    def __init__(self):
        self.filler_patterns = [re.compile(f, re.IGNORECASE) for f in self.FILLERS]

    def clean(self, text: str) -> str:
        if not text:
            return ""

        cleaned = text
        
        # 1. Eliminar muletillas
        for pattern in self.filler_patterns:
            cleaned = pattern.sub("", cleaned)
            
        # 2. Normalizar espacios múltiples
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        
        # 3. Capitalización básica (si Whisper no lo hizo)
        if cleaned and cleaned[0].islower():
            cleaned = cleaned[0].upper() + cleaned[1:]
            
        return cleaned
