import sys
import unittest
from unittest.mock import MagicMock, patch

# Mock dependencies before importing src
sys.modules["transformers"] = MagicMock()
sys.modules["peft"] = MagicMock()
sys.modules["torch"] = MagicMock()
sys.modules["bitsandbytes"] = MagicMock()

# Mock config to avoid pydantic dependency
mock_config = MagicMock()
mock_settings = MagicMock()
mock_settings.MODEL_ID = "mock-model-id"
mock_settings.LORA_ADAPTER_PATH = "/mock/adapter/path"
mock_settings.MAX_NEW_TOKENS = 128
mock_settings.TEMPERATURE = 0.5
mock_config.get_settings.return_value = mock_settings
sys.modules["src.config"] = mock_config

import os
# Adjust path to include src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from src.inference.model_loader import ModelLoader
from src.inference.llm_engine import LLMEngine
# from src.config import get_settings # No longer needed as we mocked it

settings = mock_settings

class TestGenerativeInference(unittest.TestCase):
    
    def setUp(self):
        # Reset Singleton state before each test
        ModelLoader._instance = None
        ModelLoader.model = None
        ModelLoader.tokenizer = None

    @patch("src.inference.model_loader.AutoModelForCausalLM")
    @patch("src.inference.model_loader.AutoTokenizer")
    @patch("src.inference.model_loader.PeftModel")
    def test_model_loader_initialization(self, mock_peft, mock_tokenizer, mock_automodel):
        # Setup mocks
        mock_base_model = MagicMock()
        mock_automodel.from_pretrained.return_value = mock_base_model
        
        mock_tok_instance = MagicMock()
        mock_tokenizer.from_pretrained.return_value = mock_tok_instance
        
        mock_peft_instance = MagicMock()
        mock_peft.from_pretrained.return_value = mock_peft_instance

        # Act
        loader = ModelLoader()
        
        # Assert - Base Model Loaded
        mock_automodel.from_pretrained.assert_called()
        _, kwargs = mock_automodel.from_pretrained.call_args
        self.assertTrue(kwargs["quantization_config"].load_in_4bit)
        
        # Assert - Tokenizer Loaded
        mock_tokenizer.from_pretrained.assert_called_with(settings.MODEL_ID, trust_remote_code=True)
        
        # Assert - Adapter Attached
        mock_peft.from_pretrained.assert_called_with(mock_base_model, settings.LORA_ADAPTER_PATH)
        
        # Assert - Singleton holds the model
        self.assertEqual(loader.get_model(), mock_peft_instance)
        self.assertEqual(loader.get_tokenizer(), mock_tok_instance)

    @patch("src.inference.model_loader.AutoModelForCausalLM")
    @patch("src.inference.model_loader.AutoTokenizer")
    @patch("src.inference.model_loader.PeftModel")
    def test_llm_engine_generation(self, mock_peft, mock_tokenizer, mock_automodel):
        # Ensure ModelLoader is fresh or mocked
        ModelLoader._instance = None
        
        mock_model = MagicMock()
        mock_peft.from_pretrained.return_value = mock_model
        
        mock_tok = MagicMock()
        mock_tokenizer.from_pretrained.return_value = mock_tok
        # Mock tokenizer call
        mock_tok.return_value = MagicMock() # return tensors
        mock_tok.decode.return_value = "### Response: Formal text output"

        engine = LLMEngine()
        
        # Act
        output = engine.generate("raw input text")
        
        # Assert
        mock_model.generate.assert_called()
        self.assertEqual(output, "Formal text output")

if __name__ == '__main__':
    unittest.main()
