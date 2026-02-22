import pytest
import sys
from unittest.mock import MagicMock, patch

# Mock unsloth and trl since they might not be installed or require GPU
sys.modules["unsloth"] = MagicMock()
sys.modules["trl"] = MagicMock()
sys.modules["transformers"] = MagicMock()
sys.modules["datasets"] = MagicMock()
sys.modules["torch"] = MagicMock()

# Now import the script under test
# We need to make sure we can import from src
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

# Re-import to apply mocks
from src.training.train import train

@patch("src.training.train.FastLanguageModel")
@patch("src.training.train.SFTTrainer")
@patch("src.training.train.load_dataset")
def test_train_dry_run(mock_load_dataset, mock_sft_trainer, mock_fast_model):
    """
    Verifies that train.py calls the necessary libraries with correct parameters.
    """
    # Setup Mocks
    mock_model = MagicMock()
    mock_tokenizer = MagicMock()
    mock_fast_model.from_pretrained.return_value = (mock_model, mock_tokenizer)
    
    # Mock the PEFT model returned
    mock_peft_model = MagicMock()
    mock_fast_model.get_peft_model.return_value = mock_peft_model
    
    mock_trainer_instance = MagicMock()
    mock_sft_trainer.return_value = mock_trainer_instance
    
    # Run Script
    train(
        dataset_path="mock_train.jsonl",
        val_dataset_path="mock_val.jsonl",
        output_dir="mock_output",
        max_seq_length=128
    )
    
    # Assertions
    # 1. Check Model Loading
    mock_fast_model.from_pretrained.assert_called_once()
    _, kwargs = mock_fast_model.from_pretrained.call_args
    assert kwargs["model_name"] == "unsloth/llama-3-8b-Instruct-bnb-4bit"
    assert kwargs["load_in_4bit"] is True
    
    # 2. Check LoRA Config
    mock_fast_model.get_peft_model.assert_called_once()
    
    # 3. Check Dataset Loading
    mock_load_dataset.assert_called_once_with("json", data_files={"train": "mock_train.jsonl", "validation": "mock_val.jsonl"})
    
    # 4. Check Trainer Initialization
    mock_sft_trainer.assert_called_once()
    
    # 5. Check Train Loop
    mock_trainer_instance.train.assert_called_once()
    
    # 6. Check Saving - Should be called on the PEFT model now
    mock_peft_model.save_pretrained.assert_called_with("mock_output")
    mock_tokenizer.save_pretrained.assert_called_with("mock_output")