import pytest
import os
import shutil
import zipfile
from lxml import etree
from src.mining.analyzer import CorpusAnalyzer
from src.mining.synthesizer import SkeletonSynthesizer
from src.core.constants import PATH_WORD_DOCUMENT

# Mock XML Content
MOCK_XML_A = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p w:rsidR="00123456"><w:r><w:t>Header: Fixed Content</w:t></w:r></w:p>
        <w:p w:rsidR="00123456"><w:r><w:t>Dynamic Content A</w:t></w:r></w:p>
        <w:p w:rsidR="00123456"><w:r><w:t>Footer: Fixed Content</w:t></w:r></w:p>
    </w:body>
</w:document>"""

MOCK_XML_B = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p w:rsidR="00999999"><w:r><w:t>Header: Fixed Content</w:t></w:r></w:p>
        <w:p w:rsidR="00999999"><w:r><w:t>Dynamic Content B</w:t></w:r></w:p>
        <w:p w:rsidR="00999999"><w:r><w:t>Footer: Fixed Content</w:t></w:r></w:p>
    </w:body>
</w:document>"""

MOCK_XML_C = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:body>
        <w:p w:rsidR="00888888"><w:r><w:t>Header: Fixed Content</w:t></w:r></w:p>
        <w:p w:rsidR="00888888"><w:r><w:t>Dynamic Content C</w:t></w:r></w:p>
        <w:p w:rsidR="00888888"><w:r><w:t>Footer: Fixed Content</w:t></w:r></w:p>
    </w:body>
</w:document>"""

@pytest.fixture
def mock_corpus_dir(tmp_path):
    """Creates a temporary directory with 3 mock .docx files."""
    corpus_dir = tmp_path / "corpus"
    corpus_dir.mkdir()
    
    xmls = {
        "doc_a.docx": MOCK_XML_A,
        "doc_b.docx": MOCK_XML_B,
        "doc_c.docx": MOCK_XML_C
    }
    
    file_paths = []
    
    for filename, xml_content in xmls.items():
        docx_path = corpus_dir / filename
        with zipfile.ZipFile(docx_path, 'w') as zf:
            zf.writestr(PATH_WORD_DOCUMENT, xml_content)
            # Create a minimal _rels/.rels or just enough to be parsed by our robust tools? 
            # Our analyzer ONLY reads word/document.xml, so strict validity isn't required for unit tests of logic.
        file_paths.append(str(docx_path))
        
    return file_paths

def test_normalization_and_hashing():
    """Test T01a: Normalization logic."""
    analyzer = CorpusAnalyzer()
    
    # Parse two XMLs that differ only in RSID
    xml1 = b'<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:rsidR="001"><w:r><w:t> Test </w:t></w:r></w:p>'
    xml2 = b'<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" w:rsidR="002"><w:r><w:t>Test</w:t></w:r></w:p>'
    
    parser = etree.XMLParser(remove_blank_text=True)
    node1 = etree.fromstring(xml1, parser=parser)
    node2 = etree.fromstring(xml2, parser=parser)
    
    norm1 = analyzer._normalize_node(node1)
    norm2 = analyzer._normalize_node(node2)
    
    hash1 = analyzer._compute_hash(norm1)
    hash2 = analyzer._compute_hash(norm2)
    
    assert hash1 == hash2, "Normalization should produce identical hashes for content-equivalent nodes"

def test_frequency_analysis(mock_corpus_dir):
    """Test T01a: Frequency Maps."""
    analyzer = CorpusAnalyzer()
    freq_map = analyzer.analyze(mock_corpus_dir)
    
    # We expect:
    # Header: 3 occurrences (100%)
    # Footer: 3 occurrences (100%)
    # Dynamic A, B, C: 1 occurrence each (33%)
    
    static_count = 0
    dynamic_count = 0
    
    for f in freq_map.values():
        if f['frequency'] == 1.0:
            static_count += 1
            # Verify it's actually Header or Footer
            xml = f['xml_repr']
            assert "Fixed Content" in xml
        elif f['frequency'] <= 0.34:
             dynamic_count += 1
             xml = f['xml_repr']
             assert "Dynamic Content" in xml
             
    assert static_count == 2, f"Expected 2 static nodes, found {static_count}"
    assert dynamic_count == 3, f"Expected 3 dynamic nodes, found {dynamic_count}"

def test_synthesis(mock_corpus_dir, tmp_path):
    """Test T01b: Full Reconstruction."""
    analyzer = CorpusAnalyzer()
    freq_map = analyzer.analyze(mock_corpus_dir)
    
    synthesizer = SkeletonSynthesizer(freq_map, threshold=0.9)
    base_doc = mock_corpus_dir[0] # doc_a
    output_path = tmp_path / "master_skeleton.xml"
    
    result = synthesizer.synthesize(base_doc, str(output_path))
    
    assert result['static_nodes'] == 2
    assert result['dynamic_nodes'] == 1
    
    # Read output
    with open(output_path, 'rb') as f:
        output_xml = f.read().decode('utf-8')
        
    assert "Fixed Content" in output_xml
    assert "Dynamic Content" not in output_xml
    assert "{{DYNAMIC_CONTENT}}" in output_xml
