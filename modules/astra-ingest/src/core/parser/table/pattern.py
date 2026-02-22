from typing import Optional
from lxml import etree
from src.core.constants import OOXML_NAMESPACES

class RowPatternDetector:
    """
    Identifica cuál fila de la tabla sirve como 'Template Row' para la inyección de datos.
    """
    
    def __init__(self):
        self.ns = OOXML_NAMESPACES

    def detect_template_row(self, table_node: etree._Element, is_complex: bool) -> Optional[int]:
        """
        Retorna el índice de la fila candidata.
        Retorna None si no se puede determinar un patrón seguro.
        """
        # Si la tabla es compleja, no intentamos adivinar patrones dinámicos
        if is_complex:
            return None

        rows = table_node.xpath('./w:tr', namespaces=self.ns)
        row_count = len(rows)

        # Regla 1: Tablas muy pequeñas (0 o 1 fila) son estáticas
        if row_count < 2:
            return None

        # Regla 2: Heurística Estándar (Header + Data)
        # Asumimos que la primera fila (0) es encabezado.
        # La segunda fila (1) es la candidata a patrón de datos.
        # En el futuro, esto podría usar NLP para comparar similitud de estilo entre Fila 1 y Fila 2.
        
        return 1