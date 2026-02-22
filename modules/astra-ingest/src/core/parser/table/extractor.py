import uuid
import copy
from typing import Tuple, Optional
from lxml import etree
from src.core.constants import OOXML_NAMESPACES

class TemplateRowExtractor:
    """
    Extrae, limpia y marca la fila molde de una tabla dinámica.
    """

    def __init__(self):
        self.ns = OOXML_NAMESPACES
        self.w = f"{{{self.ns['w']}}}"
        self.ASTRA_NS = "https://astra.ai/ooxml"
        self.ASTRA_PREFIX = "{https://astra.ai/ooxml}"

    def extract_and_mark(self, table_node: etree._Element, row_index: int) -> Tuple[Optional[bytes], Optional[str]]:
        """
        1. Clona la fila en row_index.
        2. Limpia el texto de la copia (mantiene estilos).
        3. Marca la tabla original con astra:tblId.
        
        Returns: (xml_bytes_fila, uuid_tabla)
        """
        rows = table_node.xpath('./w:tr', namespaces=self.ns)
        
        if row_index >= len(rows):
            return None, None

        # 1. Clonar la fila objetivo
        target_row = rows[row_index]
        template_row = copy.deepcopy(target_row)

        # 2. Sanitización: Vaciar el contenido de texto <w:t>
        # Manteniendo <w:p>, <w:r>, <w:pPr>, <w:rPr> intactos para preservar estilos.
        w_t_tag = f"{self.w}t"
        
        for text_node in template_row.iter(w_t_tag):
            # Opción A: Vaciar texto
            text_node.text = ""
            # Opción B (Opcional): Poner un marcador visual si se desea debugging
            # text_node.text = "{DATA}" 

        # Agregar marcador de tipo al XML de la fila (para el Builder)
        template_row.set(f"{self.ASTRA_PREFIX}rowType", "template")

        # 3. Marcaje: Inyectar ID en la tabla original
        tbl_uuid = str(uuid.uuid4())
        
        # Asegurar que el namespace esté registrado en el nodo raíz de la tabla si no lo está
        # (lxml maneja esto al serializar si usamos el nombre cualificado)
        table_node.set(f"{self.ASTRA_PREFIX}tblId", tbl_uuid)

        # Serializar la fila plantilla
        xml_bytes = etree.tostring(template_row, encoding='utf-8')

        return xml_bytes, tbl_uuid