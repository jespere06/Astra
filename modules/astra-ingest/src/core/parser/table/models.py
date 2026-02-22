from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class TableComplexityReport:
    is_complex: bool
    reasons: List[str] = field(default_factory=list)

@dataclass
class RowClassification:
    """Clasificación de índices de filas dentro de una tabla."""
    header_indices: List[int] = field(default_factory=list)
    body_indices: List[int] = field(default_factory=list)
    footer_indices: List[int] = field(default_factory=list)

@dataclass
class TableAnalysisResult:
    table_node_id: str  # ID original (rsidR) o generado
    is_dynamic_candidate: bool
    complexity_report: TableComplexityReport
    template_row_index: Optional[int] = None
    astra_id: Optional[str] = None  # UUID inyectado
    xml_template_row: Optional[bytes] = None  # XML de la fila molde
    row_classification: Optional[RowClassification] = None # Nueva clasificación