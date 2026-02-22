import pytest
import numpy as np
from unittest.mock import MagicMock, AsyncMock
from src.core.validator import SemanticValidator

# Mock embedding for "Sentence A"
VEC_A = np.array([1.0, 0.0, 0.0], dtype=np.float32)
# Mock embedding for "Sentence B" (High sim)
VEC_B = np.array([0.9, 0.1, 0.0], dtype=np.float32)
# Mock embedding for "Sentence C" (Low sim)
VEC_C = np.array([0.0, 1.0, 0.0], dtype=np.float32)
# Mock embedding for "Sentence D" (Ambiguous)
VEC_D = np.array([0.6, 0.8, 0.0], dtype=np.float32)

@pytest.fixture
def validator():
    v = SemanticValidator(model_name="mock-model")
    # Mock the SentenceTransformer model
    v.model = MagicMock()
    v.model.encode = MagicMock(side_effect=lambda texts, convert_to_tensor=False: [
        VEC_A if texts[0] == "text_a" else VEC_D, # simple logic for mock
        VEC_B if texts[1] == "text_b" else (VEC_C if texts[1] == "text_c" else VEC_D)
    ])
    
    # Mock the LLMJudge
    v.judge = AsyncMock()
    return v

@pytest.mark.asyncio
async def test_validate_pair_green(validator):
    # Setup mock for high similarity
    # We overwrite the Encode mock for simplicity per test
    validator.model.encode = MagicMock(return_value=[VEC_A, VEC_B]) # Dot prod ~0.9
    
    result = await validator.validate_pair("text_a", "text_b", current_start=10.0)
    
    assert result["status"] == "GREEN"
    assert result["source"] == "EMBEDDING"
    assert result["score"] > 0.85

@pytest.mark.asyncio
async def test_validate_pair_red(validator):
    # Setup mock for low similarity
    validator.model.encode = MagicMock(return_value=[VEC_A, VEC_C]) # Dot prod 0.0
    
    result = await validator.validate_pair("text_a", "text_c", current_start=10.0)
    
    assert result["status"] == "RED"
    assert result["source"] == "EMBEDDING"
    assert result["score"] < 0.4

@pytest.mark.asyncio
async def test_validate_pair_temporal_error(validator):
    # Timestamps inconsistency
    result = await validator.validate_pair("text_a", "text_b", current_start=5.0, last_valid_end=10.0)
    
    assert result["status"] == "RED"
    assert "Temporal Inconsistency" in result["reasoning"]
    assert result["source"] == "TEMPORAL"

@pytest.mark.asyncio
async def test_validate_pair_yellow_llm_green(validator):
    # Ambiguous embeddings -> LLM High Score
    validator.model.encode = MagicMock(return_value=[VEC_A, VEC_D]) # Dot prod ~0.6
    validator.judge.evaluate.return_value = {"score": 0.9, "reasoning": "Excellent match"}
    
    result = await validator.validate_pair("text_a", "text_d", current_start=10.0)
    
    assert result["status"] == "GREEN"
    assert result["source"] == "LLM"
    assert result["score"] == 0.9

@pytest.mark.asyncio
async def test_validate_pair_yellow_llm_yellow(validator):
    # Ambiguous embeddings -> LLM Ambiguous
    validator.model.encode = MagicMock(return_value=[VEC_A, VEC_D]) 
    validator.judge.evaluate.return_value = {"score": 0.5, "reasoning": "Unsure"}
    
    result = await validator.validate_pair("text_a", "text_d", current_start=10.0)
    
    assert result["status"] == "YELLOW"
    assert result["source"] == "LLM"
