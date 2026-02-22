import logging
from typing import List
from lxml import etree
from src.core.constants import OOXML_NAMESPACES
from src.core.parser.table.models import RowClassification

logger = logging.getLogger(__name__)

class TableStandardizer:
    """
    Motor de modificación física del árbol XML de tablas.
    Responsable de podar datos existentes e inyectar la fila molde marcada.
    """

    def __init__(self):
        self.ns = OOXML_NAMESPACES
        self.w = f"{{{self.ns['w']}}}"
        self.ASTRA_URI = "https://astra.ai/ooxml"
        self.ASTRA_PREFIX = f"{{{self.ASTRA_URI}}}"

    def standardize_table(self, 
                          table_node: etree._Element, 
                          classification: RowClassification, 
                          template_row_xml: bytes) -> etree._Element:
        """
        Transforma una tabla poblada en una tabla esqueleto.
        
        1. Elimina todas las filas clasificadas como BODY.
        2. Inyecta la fila molde con el atributo astra:rowType="template".
        3. Preserva Headers y Footers.
        """
        if not classification.body_indices:
            logger.warning("No se identificaron filas de cuerpo para podar. La tabla no se modificará.")
            return table_node

        # 1. Preparar la Fila Molde
        try:
            # Parseamos el XML sanitizado que viene del Extractor
            template_node = etree.fromstring(template_row_xml)
        except etree.XMLSyntaxError as e:
            logger.error(f"Error parseando XML de fila molde: {e}")
            raise ValueError("El XML de la fila molde está corrupto.")

        # Inyectar el atributo marcador para el Builder
        template_node.set(f"{self.ASTRA_PREFIX}rowType", "template")

        # 2. Obtener referencias actuales de las filas
        rows = table_node.xpath('./w:tr', namespaces=self.ns)
        
        # Validar consistencia de índices
        max_idx = len(rows) - 1
        all_indices = classification.header_indices + classification.body_indices + classification.footer_indices
        if any(idx > max_idx for idx in all_indices):
            logger.error(f"Índices de clasificación fuera de rango para tabla con {len(rows)} filas.")
            return table_node

        # 3. Poda (Eliminación de filas de datos)
        deleted_count = 0
        for idx in classification.body_indices:
            row_to_remove = rows[idx]
            if row_to_remove.getparent() == table_node:
                table_node.remove(row_to_remove)
                deleted_count += 1

        logger.info(f"Se podaron {deleted_count} filas de datos de la tabla.")

        # 4. Inserción de la Fila Molde
        if classification.header_indices:
            last_header_idx = classification.header_indices[-1]
            last_header_node = rows[last_header_idx]
            last_header_node.addnext(template_node)
        else:
            first_existing_tr = table_node.find(f"{self.w}tr")
            if first_existing_tr is not None:
                first_existing_tr.addprevious(template_node)
            else:
                table_node.append(template_node)

        return table_node
