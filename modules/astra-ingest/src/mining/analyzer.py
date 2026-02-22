"""
CorpusAnalyzer — ASTRA-MINER

Analyzes a corpus of .docx files to determine structural frequency of XML nodes.
Uses DocxAtomizer for ZIP/XML parsing (DRY principle per narrative).

DTM Contract:
    analyze(file_paths) -> FrequencyMap {hash -> {count, doc_ids, frequency, xml_repr, tag}}
"""
import hashlib
import logging
from typing import List, Dict, Any
from lxml import etree

from src.core.parser.xml_engine import DocxAtomizer
from src.core.constants import OOXML_NAMESPACES

logger = logging.getLogger(__name__)


class CorpusAnalyzer:
    """
    Analyzes a corpus of .docx files to determine structural frequency of nodes.
    """

    def __init__(self):
        self.node_frequencies: Dict[str, Dict[str, Any]] = {}
        self.total_docs = 0

    def analyze(self, file_paths: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Main entry point. Processes a list of .docx files and returns the frequency map.
        """
        self.total_docs = len(file_paths)
        logger.info(f"Starting analysis of {self.total_docs} documents.")

        for path in file_paths:
            try:
                self._process_document(path)
            except Exception as e:
                logger.error(f"Failed to process {path}: {e}")

        # Calculate percentages based on unique document appearances
        for node_hash, data in self.node_frequencies.items():
            doc_count = len(data.get('doc_ids', set()))
            data['frequency'] = doc_count / self.total_docs if self.total_docs > 0 else 0.0

        return self.node_frequencies

    def _process_document(self, path: str):
        """
        Opens a .docx via DocxAtomizer, normalizes nodes, and counts hashes.
        Tracks per-document appearances via doc_ids set.
        """
        with DocxAtomizer(path) as atomizer:
            body = atomizer.document_tree.xpath(
                '//w:body', namespaces=atomizer.namespaces
            )[0]
            doc_id = path

            for child in body:
                if child.tag.endswith('}sectPr'):
                    continue

                normalized_node = self._normalize_node(child)
                node_hash = self._compute_hash(normalized_node)

                if node_hash not in self.node_frequencies:
                    self.node_frequencies[node_hash] = {
                        "count": 0,
                        "doc_ids": set(),
                        "xml_repr": etree.tostring(normalized_node, encoding='unicode'),
                        "tag": child.tag
                    }

                self.node_frequencies[node_hash]["count"] += 1
                self.node_frequencies[node_hash]["doc_ids"].add(doc_id)

    def _normalize_node(self, node: etree._Element) -> etree._Element:
        """
        Creates a normalized copy: removes w:rsid* attributes and trims text.
        """
        clean_node = _copy_node(node)

        w_ns = OOXML_NAMESPACES['w']
        rsid_attrs = [
            f'{{{w_ns}}}rsidR',
            f'{{{w_ns}}}rsidRPr',
            f'{{{w_ns}}}rsidRDefault',
            f'{{{w_ns}}}rsidP'
        ]

        for elem in clean_node.iter():
            for attr in rsid_attrs:
                if attr in elem.attrib:
                    del elem.attrib[attr]
            if elem.text:
                elem.text = elem.text.strip()
            if elem.tail:
                elem.tail = elem.tail.strip()

        return clean_node

    def _compute_hash(self, node: etree._Element) -> str:
        """Computes SHA-256 of the Canonical XML string of the node."""
        xml_bytes = etree.tostring(node, method="c14n", exclusive=True, with_comments=False)
        return hashlib.sha256(xml_bytes).hexdigest()


def _copy_node(node):
    """Deep copy of an lxml element."""
    return etree.fromstring(etree.tostring(node))
