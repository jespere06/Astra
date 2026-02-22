"""
SkeletonSynthesizer — ASTRA-MINER

Reconstructs a Master Skeleton XML based on frequency analysis.
Uses DocxAtomizer for consistent ZIP/XML handling.

DTM Contract:
    synthesize(base_doc_path, output_path) -> {"static_nodes", "dynamic_nodes", "structural_coverage"}
"""
import logging
from typing import Dict, Any
from lxml import etree

from src.core.parser.xml_engine import DocxAtomizer
from src.core.constants import OOXML_NAMESPACES

logger = logging.getLogger(__name__)


class SkeletonSynthesizer:
    """
    Reconstructs a Master Skeleton XML based on frequency analysis.
    """

    def __init__(self, frequency_map: Dict[str, Dict[str, Any]], threshold: float = 0.9):
        self.frequency_map = frequency_map
        self.threshold = threshold
        self.w_ns = OOXML_NAMESPACES['w']

    def synthesize(self, base_doc_path: str, output_path: str) -> Dict[str, Any]:
        """
        Synthesizes the master skeleton using a base document.
        Keeps high-frequency nodes, replaces low-frequency with placeholders.
        """
        from .analyzer import CorpusAnalyzer
        analyzer = CorpusAnalyzer()

        with DocxAtomizer(base_doc_path) as atomizer:
            # Work on a copy of the tree so we don't modify the atomizer's internal state
            tree_root = atomizer.document_tree.getroot()
            # We need to serialize and re-parse to get an independent copy
            tree_copy = etree.fromstring(etree.tostring(tree_root))

            body = tree_copy.xpath('//w:body', namespaces=OOXML_NAMESPACES)[0]

            total_static = 0
            total_dynamic = 0

            for child in body:
                if child.tag.endswith('}sectPr'):
                    continue

                normalized = analyzer._normalize_node(child)
                node_hash = analyzer._compute_hash(normalized)

                freq_data = self.frequency_map.get(node_hash)

                is_static = False
                if freq_data:
                    frequency = freq_data.get('frequency', 0)
                    if frequency >= self.threshold:
                        is_static = True

                if is_static:
                    total_static += 1
                else:
                    total_dynamic += 1
                    self._replace_with_slot(child)

            # Write skeleton XML
            with open(output_path, 'wb') as f:
                f.write(etree.tostring(
                    tree_copy, encoding='UTF-8',
                    xml_declaration=True, standalone=True
                ))

            logger.info(f"Skeleton generated. Static: {total_static}, Dynamic: {total_dynamic}")
            return {
                "static_nodes": total_static,
                "dynamic_nodes": total_dynamic,
                "structural_coverage": (
                    total_static / (total_static + total_dynamic)
                    if (total_static + total_dynamic) > 0 else 0
                ),
            }

    def _replace_with_slot(self, node: etree._Element):
        """
        Replaces a node's content with a {{DYNAMIC_CONTENT}} placeholder.
        """
        w_ns = self.w_ns

        if node.tag.endswith('}p'):
            node.text = None
            for child in list(node):
                node.remove(child)
            r = etree.SubElement(node, f'{{{w_ns}}}r')
            t = etree.SubElement(r, f'{{{w_ns}}}t')
            t.text = "{{DYNAMIC_CONTENT}}"

        elif node.tag.endswith('}tbl'):
            for child in list(node):
                if child.tag.endswith('}tr'):
                    node.remove(child)
            tr = etree.SubElement(node, f'{{{w_ns}}}tr')
            tc = etree.SubElement(tr, f'{{{w_ns}}}tc')
            p = etree.SubElement(tc, f'{{{w_ns}}}p')
            r = etree.SubElement(p, f'{{{w_ns}}}r')
            t = etree.SubElement(r, f'{{{w_ns}}}t')
            t.text = "{{DYNAMIC_CONTENT_TABLE}}"
