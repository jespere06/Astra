import logging
from pathlib import Path
from typing import List, Dict, Set
from lxml import etree

from src.core.parser.xml_engine import DocxAtomizer
from src.core.constants import OOXML_NAMESPACES
from .analyzer import CorpusAnalyzer
from src.config import settings  # Importar configuración

logger = logging.getLogger(__name__)


class SemanticExtractor:
    """
    Extracts dynamic (non-skeleton) content from the corpus.
    Returns raw XML fragments with styling preserved for use as training targets.
    """

    def __init__(self, static_hashes: Set[str], threshold: float = None):
        self.static_hashes = static_hashes
        # Usar config si no se provee un threshold explícito
        self.threshold = threshold if threshold is not None else 0.85
        self.analyzer = CorpusAnalyzer()

    def extract_from_document(self, path: str) -> List[Dict[str, str]]:
        """
        Extracts dynamic XML fragments from a single .docx file.

        Returns:
            List of {"text": str, "xml": str, "index": int}
            where xml includes <w:pPr> styling.
        """
        extracted = []

        with DocxAtomizer(path) as atomizer:
            body = atomizer.document_tree.xpath(
                '//w:body', namespaces=atomizer.namespaces
            )[0]

            for idx, child in enumerate(body):
                if child.tag.endswith('}sectPr'):
                    continue

                # Hash using same normalization as CorpusAnalyzer
                normalized = self.analyzer._normalize_node(child)
                node_hash = self.analyzer._compute_hash(normalized)

                # Skip skeleton (static) nodes
                if node_hash in self.static_hashes:
                    continue

                # Extract text content
                text = " ".join(
                    child.xpath('.//w:t/text()', namespaces=OOXML_NAMESPACES)
                )

                # Filter trivial content
                # TODO: Mover este '10' a config si se desea mayor control
                if len(text.strip()) < 10:
                    continue

                # Get the raw XML string (preserving <w:pPr> styles)
                raw_xml = etree.tostring(child, encoding='unicode')

                extracted.append({
                    "text": text.strip(),
                    "xml": raw_xml,
                    "index": idx,
                })

        return extracted

    def extract_from_corpus(self, file_paths: List[str]) -> Dict[str, List[Dict]]:
        """
        Extracts dynamic XML fragments from all documents.

        Returns:
            Dict mapping filename stem -> List of extracted fragments.
        """
        corpus = {}
        for path in file_paths:
            try:
                stem = Path(path).stem
                fragments = self.extract_from_document(path)
                corpus[stem] = fragments
                logger.info(f"Extracted {len(fragments)} dynamic fragments from {stem}")
            except Exception as e:
                logger.warning(f"Failed to extract from {path}: {e}")
        return corpus
