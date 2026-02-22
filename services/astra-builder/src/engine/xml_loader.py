from lxml import etree
from typing import Dict, Optional

class XMLLoader:
    """
    Parses and indexes OOXML document.xml content for efficient node retrieval.
    """
    
    NAMESPACES = {
        'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
        'astra': 'http://schemas.astra.ai/2026/main' # Hypothetical namespace for explicit IDs
    }

    def __init__(self, xml_content: bytes):
        """
        Args:
            xml_content: The raw bytes of document.xml
        """
        self.tree = etree.fromstring(xml_content)
        self._id_map: Dict[str, etree._Element] = {}
        self._index_document()

    def _index_document(self):
        """
        Traverses the XML tree and indexes nodes by 'astra:id' or 'w:rsidR'.
        Prioritizes 'astra:id' if present (explicit anchor).
        """
        # We look for any element with identifying attributes
        # XPath could be used, but iteration is often faster for full indexing
        for elem in self.tree.iter():
            # Check for explicit ASTRA ID
            astra_id = elem.get(f"{{{self.NAMESPACES['astra']}}}id")
            if astra_id:
                self._id_map[astra_id] = elem
                continue

            # Fallback: Index by RSID (Revision Save ID) if useful for patching
            # Note: RSIDs are not unique per document, so this is a 1-to-many potentially
            # For this implementation, we assume we might want to target specific RSIDs
            # or we just rely on explicit astra:ids for the main logic.
            # We'll skip RSID indexing for now unless explicitly needed to keep map clean.
            pass

    def get_node_by_id(self, anchor_id: str) -> Optional[etree._Element]:
        """
        Retrieves a node by its unique anchor ID.
        """
        return self._id_map.get(anchor_id)

    def to_string(self) -> bytes:
        """
        Serializes the modified XML tree back to bytes.
        """
        return etree.tostring(self.tree, encoding='UTF-8', standalone=True)
