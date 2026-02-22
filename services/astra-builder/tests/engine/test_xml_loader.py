import unittest
from lxml import etree
import sys
import os

# Adjust path to include src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.engine.xml_loader import XMLLoader

class TestXMLLoader(unittest.TestCase):
    
    def setUp(self):
        # Create a dummy XML with known IDs
        self.xml_content = b"""
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                    xmlns:astra="http://schemas.astra.ai/2026/main">
            <w:body>
                <w:p astra:id="anchor-1">
                    <w:r>
                        <w:t>Static Text</w:t>
                    </w:r>
                </w:p>
                <w:p>
                    <w:r astra:id="anchor-2">
                        <w:t>Another Static</w:t>
                    </w:r>
                </w:p>
            </w:body>
        </w:document>
        """
        self.loader = XMLLoader(self.xml_content)

    def test_index_document(self):
        # Verify that anchor-1 and anchor-2 are indexed
        node1 = self.loader.get_node_by_id("anchor-1")
        self.assertIsNotNone(node1)
        self.assertEqual(node1.tag, f"{{{self.loader.NAMESPACES['w']}}}p")
        
        node2 = self.loader.get_node_by_id("anchor-2")
        self.assertIsNotNone(node2)
        self.assertEqual(node2.tag, f"{{{self.loader.NAMESPACES['w']}}}r")

    def test_get_node_by_id_missing(self):
        node = self.loader.get_node_by_id("non-existent")
        self.assertIsNone(node)

if __name__ == '__main__':
    unittest.main()
