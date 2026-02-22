import unittest
import shutil
import os
import json
import zipfile
from pathlib import Path
from lxml import etree
import sys

# Adjust path to include src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

from src.mining.pipeline import DataMiningPipeline

class TestDataMiningPipeline(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = Path("tests/temp_pipeline")
        self.docs_dir = self.test_dir / "docs"
        self.meta_dir = self.test_dir / "transcripts"
        self.out_dir = self.test_dir / "output"
        
        # Cleanup and create dirs
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
        self.docs_dir.mkdir(parents=True)
        self.meta_dir.mkdir(parents=True)
        self.out_dir.mkdir(parents=True)
        
        # Create a dummy .docx
        self._create_dummy_docx(self.docs_dir / "doc1.docx", "Test Content")
        
        # Create a matching transcript
        transcript = [{"text": "Test Content", "speaker": "A", "start": 0, "end": 1}]
        with open(self.meta_dir / "doc1.json", "w") as f:
            json.dump(transcript, f)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def _create_dummy_docx(self, path, text):
        document_xml = f"""
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
            <w:body>
                <w:p>
                    <w:r>
                        <w:t>{text}</w:t>
                    </w:r>
                </w:p>
            </w:body>
        </w:document>
        """
        with zipfile.ZipFile(path, 'w') as zf:
            zf.writestr('word/document.xml', document_xml.strip())
            # Minimal Content Types 
            zf.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>')

    def test_pipeline_execution(self):
        # Run pipeline
        pipeline = DataMiningPipeline(
            str(self.docs_dir), 
            str(self.meta_dir), 
            str(self.out_dir)
        )
        pipeline.run()
        
        # Verify output
        output_file = self.out_dir / "train.jsonl"
        self.assertTrue(output_file.exists())
        
        with open(output_file, 'r') as f:
            lines = f.readlines()
            self.assertGreater(len(lines), 0)
            data = json.loads(lines[0])
            self.assertIn("Test Content", data["input"])
            # Verify Sequence Learning injection
            self.assertTrue(data["input"].startswith("Order: 0/1"), f"Input should start with Order info. Got: {data['input']}")
            # Assuming alignment found it
            # Since docx text matches transcript text perfectly, score should be high.

if __name__ == '__main__':
    unittest.main()
