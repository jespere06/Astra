import pytest
import json
import zipfile
from lxml import etree
from src.mining.extractor import SemanticExtractor
from src.mining.noise_engine import NoiseInjector
from src.mining.dataset_builder import DatasetBuilder
from src.core.constants import PATH_WORD_DOCUMENT, OOXML_NAMESPACES

# Reuse Mock Data logic or create fresh fixtures
MOCK_BODY_XML = b"""
<w:body xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:p w:rsidR="001"><w:r><w:t>Header: Fixed Content</w:t></w:r></w:p>
    <w:p w:rsidR="002"><w:r><w:t>El Concejal vota positivo el Articulo 5.</w:t></w:r></w:p>
    <w:p w:rsidR="003"><w:r><w:t>Footer: Fixed Content</w:t></w:r></w:p>
</w:body>
"""

@pytest.fixture
def mock_docx(tmp_path):
    p = tmp_path / "mock.docx"
    with zipfile.ZipFile(p, 'w') as zf:
        xml = b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">' + MOCK_BODY_XML + b'</w:document>'
        zf.writestr(PATH_WORD_DOCUMENT, xml)
    return str(p)

@pytest.fixture
def mock_freq_map():
    # Simulate that Header/Footer are static (known hash)
    # We need to compute their hashes to match what Extractor will compute.
    # Use CorpusAnalyzer helper to compute hashes of the strings above.
    
    from src.mining.analyzer import CorpusAnalyzer
    tokenizer = CorpusAnalyzer()
    
    # Manually constructing expected hashes if we knew them, 
    # but better to let analyzer compute them from the mock nodes
    parser = etree.XMLParser(remove_blank_text=True)
    body = etree.fromstring(MOCK_BODY_XML, parser=parser)
    
    hashes = {}
    for child in body:
        norm = tokenizer._normalize_node(child)
        h = tokenizer._compute_hash(norm)
        # Assume first and last are static
        text = "".join(child.xpath('.//w:t/text()', namespaces=OOXML_NAMESPACES))
        if "Fixed Content" in text:
            hashes[h] = {"frequency": 1.0}
        else:
            hashes[h] = {"frequency": 0.1}
            
    return hashes

def test_semantic_extractor(mock_docx, mock_freq_map):
    extractor = SemanticExtractor(mock_freq_map, threshold=0.9)
    results = extractor.extract_from_corpus([mock_docx])
    
    assert len(results) == 1
    assert "El Concejal vota positivo" in results[0]
    assert "Header" not in results[0]
    assert "Footer" not in results[0]

def test_noise_injector():
    injector = NoiseInjector(seed=42)
    
    text = "El Artículo 5 se aprueba."
    
    # Test individual components
    assert injector.strip_formatting(text) == "el artículo 5 se aprueba"
    assert injector.expand_numbers("Artículo 5") == "Artículo cinco"
    
    # Test full corruption
    dirty = injector.corrupt(text)
    # "El" -> "el", "Artículo" -> "artículo", "5" -> "cinco", "." -> removed
    # Fillers might be added.
    
    assert "artículo" in dirty # Lowercased
    assert "cinco" in dirty    # Expanded
    assert "." not in dirty    # Stripped punctuation

def test_dataset_builder(tmp_path, mock_docx, mock_freq_map):
    extractor = SemanticExtractor(mock_freq_map)
    injector = NoiseInjector(seed=42)
    builder = DatasetBuilder(extractor, injector)
    
    output_dir = tmp_path / "dataset"
    builder.build_dataset([mock_docx], str(output_dir), augment_factor=2)
    
    train_file = output_dir / "train.jsonl"
    val_file = output_dir / "val.jsonl"
    
    assert train_file.exists()
    assert val_file.exists()
    
    # Count lines
    with open(train_file) as f:
        train_lines = f.readlines()
    with open(val_file) as f:
        val_lines = f.readlines()
        
    total = len(train_lines) + len(val_lines)
    # 1 valid text * 2 augmentations = 2 entries?
    # Wait, loop: for clean in clean_texts: add original? No, prompt implementation said:
    # "Generate N variations".
    # And my implementation: "for _ in range(augment_factor): dirty = ..."
    # So 1 clean * 2 factor = 2 lines.
    
    assert total == 2
    
    # Check JSON structure
    entry = json.loads(train_lines[0]) if train_lines else json.loads(val_lines[0])
    assert "instruction" in entry
    assert "input" in entry
    assert "output" in entry
    assert entry["output"] == "El Concejal vota positivo el Articulo 5."
