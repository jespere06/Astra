from lxml import etree
from src.core.parser.table.models import TableAnalysisResult
from src.core.parser.table.complexity import TableComplexityScanner
from src.core.parser.table.pattern import RowPatternDetector
from src.core.parser.table.extractor import TemplateRowExtractor
from src.core.constants import OOXML_NAMESPACES

class TableAnalyzer:
    def __init__(self):
        self.complexity_scanner = TableComplexityScanner()
        self.pattern_detector = RowPatternDetector()
        self.extractor = TemplateRowExtractor()
        self.w = f"{{{OOXML_NAMESPACES['w']}}}"

    def analyze_table(self, table_node: etree._Element) -> TableAnalysisResult:
        """
        Ejecuta el pipeline completo de análisis sobre un nodo <w:tbl>.
        Modifica el nodo in-place (inyectando ID) si es dinámica.
        """
        # Obtener ID existente o temporal
        node_id = table_node.get(f'{self.w}rsidR') or "unknown"

        # 1. Análisis de Complejidad
        complexity_report = self.complexity_scanner.scan(table_node)

        # 2. Detección de Patrón
        template_row_idx = self.pattern_detector.detect_template_row(
            table_node, 
            complexity_report.is_complex
        )

        is_dynamic = (template_row_idx is not None)
        astra_id = None
        xml_template = None

        # 3. Extracción y Marcaje (Solo si es candidata)
        if is_dynamic:
            xml_template, astra_id = self.extractor.extract_and_mark(
                table_node, 
                template_row_idx
            )

        return TableAnalysisResult(
            table_node_id=node_id,
            is_dynamic_candidate=is_dynamic,
            complexity_report=complexity_report,
            template_row_index=template_row_idx,
            astra_id=astra_id,
            xml_template_row=xml_template
        )