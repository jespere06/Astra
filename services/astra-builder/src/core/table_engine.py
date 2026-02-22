import copy
import logging
from lxml import etree
from src.core.constants import OOXML_NAMESPACES
from src.core.xml_sanitizer import XmlSanitizer

logger = logging.getLogger(__name__)

class DynamicTableEngine:
    """
    Clona filas máster marcadas con astra:rowType='template' y mapea datos.
    """
    def __init__(self):
        self.ns = OOXML_NAMESPACES
        self.astra_attr = f"{{{self.ns['astra']}}}rowType"
        self.w_t = f"{{{self.ns['w']}}}t"

    def process_table(self, table_node: etree._Element, row_data: list[dict]):
        """
        Expande la tabla basándose en los datos.
        """
        # 1. Encontrar la fila plantilla
        template_row = None
        for row in table_node.findall(f".//w:tr", namespaces=self.ns):
            if row.get(self.astra_attr) == "template":
                template_row = row
                break
        
        if template_row is None:
            logger.warning("No se encontró fila plantilla (astra:rowType='template') en la tabla dinámica.")
            return

        # 2. Desacoplar plantilla (la removemos para usarla de molde)
        parent = template_row.getparent()
        parent.remove(template_row)

        # 3. Iterar datos y clonar
        for data_item in row_data:
            new_row = copy.deepcopy(template_row)
            
            # Limpiar atributo de plantilla para que sea una fila normal
            if self.astra_attr in new_row.attrib:
                del new_row.attrib[self.astra_attr]
            
            # 4. Inyección de valores en celdas
            # Asumimos que la plantilla tiene placeholders tipo {{KEY}} en los nodos <w:t>
            for text_node in new_row.iter(self.w_t):
                if text_node.text:
                    original_text = text_node.text
                    for key, val in data_item.items():
                        placeholder = f"{{{{{key}}}}}" # {{KEY}}
                        if placeholder in original_text:
                            # Sanitizar antes de inyectar
                            safe_val = XmlSanitizer.sanitize(str(val))
                            original_text = original_text.replace(placeholder, safe_val)
                    text_node.text = original_text
            
            # 5. Append al final de la tabla
            parent.append(new_row)
