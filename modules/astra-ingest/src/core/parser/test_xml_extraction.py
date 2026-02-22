import unittest
import zipfile
import io
import sys
import os

# Adjust path to include src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from lxml import etree
from src.core.parser.xml_engine import DocxAtomizer

def create_dummy_docx(content_xml: str) -> io.BytesIO:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as zf:
        zf.writestr('word/document.xml', content_xml)
        zf.writestr('[Content_Types].xml', '<Types></Types>')
    buffer.seek(0)
    return buffer

class TestDocxRawExtraction(unittest.TestCase):
    
    def test_extract_raw_xml_blocks(self):
        """
        Verifies that extract_raw_xml_blocks returns the raw XML of paragraphs
        including their style properties (w:pPr).
        """
        xml_content = (
            b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            b'  <w:body>'
            b'    <w:p w:rsidR="P1">'
            b'      <w:pPr>'
            b'        <w:pStyle w:val="Heading1"/>'
            b'        <w:jc w:val="center"/>'
            b'      </w:pPr>'
            b'      <w:r>'
            b'        <w:t>Title Text</w:t>'
            b'      </w:r>'
            b'    </w:p>'
            b'    <w:p w:rsidR="P2">'
            b'      <w:r>'
            b'        <w:t>Body Text</w:t>'
            b'      </w:r>'
            b'    </w:p>'
            b'  </w:body>'
            b'</w:document>'
        )
        docx_file = create_dummy_docx(xml_content)

        with DocxAtomizer(docx_file) as atomizer:
            blocks = atomizer.extract_raw_xml_blocks()

            self.assertEqual(len(blocks), 2)
            
            # Check Block 1 (Heading)
            block1 = blocks[0]
            self.assertEqual(block1["id"], "P1")
            self.assertEqual(block1["text"], "Title Text")
            self.assertIn('<w:pStyle w:val="Heading1"/>', block1["xml"])
            self.assertIn('<w:jc w:val="center"/>', block1["xml"])
            self.assertIn('<w:t>Title Text</w:t>', block1["xml"])
            
            # Check Block 2 (Body)
            block2 = blocks[1]
            self.assertEqual(block2["id"], "P2")
            self.assertEqual(block2["text"], "Body Text")
            
            # Verify Namespaces are preserved (basic check)
            self.assertTrue('xmlns:w=' in block1["xml"] or 'w:p' in block1["xml"])

if __name__ == '__main__':
    unittest.main()
