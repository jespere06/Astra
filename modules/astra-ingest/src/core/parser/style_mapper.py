from typing import List, Dict
from src.core.parser.style_models import StyleDefinition

# Definición de Estilos Canónicos ASTRA
ASTRA_HEADING_1 = "ASTRA_HEADING_1"
ASTRA_HEADING_2 = "ASTRA_HEADING_2"
ASTRA_HEADING_3 = "ASTRA_HEADING_3"
ASTRA_BODY = "ASTRA_BODY"
ASTRA_LIST = "ASTRA_LIST"
ASTRA_QUOTE = "ASTRA_QUOTE"

class StyleMapper:
    def map_styles(self, styles: List[StyleDefinition]) -> Dict[str, str]:
        """
        Genera un diccionario { 'style_id_cliente': 'ASTRA_CANONICAL' }.
        """
        mapping = {}

        for style in styles:
            # Solo mapeamos estilos de párrafo para la estructura principal
            if style.type != 'paragraph':
                continue

            canonical = self._infer_canonical(style)
            mapping[style.style_id] = canonical

        return mapping

    def _infer_canonical(self, style: StyleDefinition) -> str:
        name_lower = style.name.lower()
        
        # 1. Regla: Match por Nombre (Case Insensitive)
        if "heading 1" in name_lower or "título 1" in name_lower or "titulo 1" in name_lower:
            return ASTRA_HEADING_1
        if "heading 2" in name_lower or "título 2" in name_lower or "titulo 2" in name_lower:
            return ASTRA_HEADING_2
        if "heading 3" in name_lower or "título 3" in name_lower or "titulo 3" in name_lower:
            return ASTRA_HEADING_3
        
        # 2. Regla: Listas por nombre
        if "list" in name_lower or "lista" in name_lower or "viñeta" in name_lower:
            return ASTRA_LIST
            
        # 3. Regla: Citas por nombre
        if "quote" in name_lower or "cita" in name_lower:
            return ASTRA_QUOTE

        # 4. Regla: Estructura (Outline Level)
        if style.outline_level is not None:
            if style.outline_level == 0:
                return ASTRA_HEADING_1
            elif style.outline_level == 1:
                return ASTRA_HEADING_2
            elif style.outline_level == 2:
                return ASTRA_HEADING_3

        # 5. Regla: Formato Visual (Tamaño y Peso)
        # Nota: 28 medios puntos = 14pt
        if style.font_size and style.font_size >= 28 and style.is_bold:
            return ASTRA_HEADING_1
        
        # Subtítulos visuales (ej. 13pt + Bold)
        if style.font_size and style.font_size >= 26 and style.is_bold:
            return ASTRA_HEADING_2

        # 6. Regla: Énfasis visual
        if style.is_italic and not style.is_bold:
             # Heurística débil para citas/notas si no se detectó antes
             # Solo si el nombre sugiere algo distinto a 'Normal'
             if "normal" not in name_lower:
                 return ASTRA_QUOTE

        # 7. Fallback (Fail-Safe)
        return ASTRA_BODY