import logging
from lxml import etree
from src.core.constants import OOXML_NAMESPACES
from src.core.parser.table.models import TableComplexityReport

logger = logging.getLogger(__name__)

class TableComplexityScanner:
    """
    Analiza un nodo <w:tbl> para determinar si su estructura es apta
    para ser convertida en una Tabla Dinámica (Row Repeater).
    """

    def __init__(self):
        self.ns = OOXML_NAMESPACES
        self.w = f"{{{self.ns['w']}}}"

    def scan(self, table_node: etree._Element) -> TableComplexityReport:
        reasons = []
        
        # 1. Detección de Tablas Anidadas
        # Buscamos <w:tbl> descendientes dentro de las celdas de esta tabla
        # Usamos xpath relativo para no salir del contexto
        nested_tables = table_node.xpath('.//w:tc//w:tbl', namespaces=self.ns)
        if nested_tables:
            reasons.append("NESTED_TABLE")

        # 2. Iteración sobre filas y celdas para fusiones
        rows = table_node.xpath('./w:tr', namespaces=self.ns)
        
        if not rows:
            return TableComplexityReport(is_complex=True, reasons=["EMPTY_TABLE"])

        cell_counts = []

        for row_idx, row in enumerate(rows):
            cells = row.xpath('./w:tc', namespaces=self.ns)
            
            # Conteo de celdas visuales (sin contar gridSpan aun)
            # Para una validación estricta, todas las filas deben tener el mismo número de nodos tc
            cell_counts.append(len(cells))

            for cell in cells:
                tc_pr = cell.find(f'{self.w}tcPr')
                if tc_pr is not None:
                    # 3. Fusión Vertical (vMerge)
                    v_merge = tc_pr.find(f'{self.w}vMerge')
                    if v_merge is not None:
                        # vMerge puede estar presente sin atributo 'val' (continua) o con 'restart'
                        # En ambos casos, implica complejidad vertical.
                        if "VERTICAL_MERGE" not in reasons:
                            reasons.append("VERTICAL_MERGE")

                    # 4. Fusión Horizontal (gridSpan)
                    grid_span = tc_pr.find(f'{self.w}gridSpan')
                    if grid_span is not None:
                        if "HORIZONTAL_MERGE" not in reasons:
                            reasons.append("HORIZONTAL_MERGE")

        # 5. Estructura Irregular (Filas con distinto número de columnas físicas)
        # Si hay gridSpan, los counts variarán, pero ya atrapamos gridSpan arriba.
        # Si NO hay gridSpan pero los counts varían, es una tabla malformada.
        if len(set(cell_counts)) > 1:
            if "HORIZONTAL_MERGE" not in reasons:
                reasons.append("IRREGULAR_COLUMN_COUNT")

        is_complex = len(reasons) > 0
        
        if is_complex:
            logger.debug(f"Tabla compleja detectada. Razones: {reasons}")

        return TableComplexityReport(is_complex=is_complex, reasons=reasons)