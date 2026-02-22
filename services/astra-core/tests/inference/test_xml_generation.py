import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Adjust path to include src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

# PROACTIVE MOCKING for missing dependencies
sys.modules["torch"] = MagicMock()
sys.modules["transformers"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()

# Mock src.config completely to avoid importing pydantic settings
mock_config = MagicMock()
sys.modules["src.config"] = mock_config

# Mock other potential heavy dependencies
sys.modules["peft"] = MagicMock()
sys.modules["bitsandbytes"] = MagicMock()
sys.modules["scipy"] = MagicMock()

# Now import the module under test
from src.inference.llm_engine import LLMEngine

class TestXMLGeneration(unittest.TestCase):
    
    @patch('src.inference.llm_engine.ModelLoader')
    @patch('src.inference.llm_engine.get_settings')
    def setUp(self, mock_settings, mock_loader):
        # Mock settings
        mock_settings.return_value.MAX_NEW_TOKENS = 128
        mock_settings.return_value.TEMPERATURE = 0.1
        
        # Mock ModelLoader
        self.mock_model = MagicMock()
        self.mock_tokenizer = MagicMock()
        mock_loader.return_value.model = self.mock_model
        mock_loader.return_value.tokenizer = self.mock_tokenizer
        
        # Mock TextIteratorStreamer inside the module if needed, 
        # but since we are testing non-streaming mostly, it might be fine.
        # However, generate_stream uses it. Let's mock it in sys modules above if needed, 
        # but it's already mocked via 'transformers' mock.
        
        self.engine = LLMEngine()

    def test_build_prompt_xml(self):
        prompt = self.engine._build_prompt("input text", mode="xml")
        self.assertIn("Formalize the transcription into an OOXML paragraph", prompt)
        self.assertIn("input text", prompt)

    def test_build_prompt_default(self):
        prompt = self.engine._build_prompt("input text", mode="default")
        self.assertIn("Actúa como un redactor de actas", prompt)

    def test_sanitize_xml_output(self):
        # Case 1: Pure XML
        xml = "<w:p>Text</w:p>"
        self.assertEqual(self.engine._sanitize_xml_output(xml), xml)
        
        # Case 2: Markdown block
        md_xml = "```xml\n<w:p>Text</w:p>\n```"
        self.assertEqual(self.engine._sanitize_xml_output(md_xml), "<w:p>Text</w:p>")
        
        # Case 3: Generic block
        gen_xml = "```\n<w:p>Text</w:p>\n```"
        self.assertEqual(self.engine._sanitize_xml_output(gen_xml), "<w:p>Text</w:p>")

    def test_generate_xml_mode(self):
        # Mock tokenizer encode/decode
        # The tokenizer call returns an object that has a .to("cuda") method
        mock_inputs = MagicMock()
        mock_inputs.to.return_value = mock_inputs # .to() returns self (fluent api)
        self.mock_tokenizer.return_value = mock_inputs

        self.mock_model.generate.return_value = ["fake_output"]
        
        # Mock decode output containing markdown
        raw_output = "### Response:\n```xml\n<w:p>Cleaned</w:p>\n```"
        self.mock_tokenizer.decode.return_value = raw_output
        
        # Run generate
        result = self.engine.generate("input", mode="xml")
        
        self.assertEqual(result, "<w:p>Cleaned</w:p>")

if __name__ == '__main__':
    unittest.main()
