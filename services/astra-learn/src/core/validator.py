import logging
import asyncio
from sentence_transformers import SentenceTransformer, util
import numpy as np
from src.ml.judge import LLMJudge

logger = logging.getLogger(__name__)

class SemanticValidator:
    def __init__(self, model_name="paraphrase-multilingual-MiniLM-L12-v2"):
        logger.info(f"Loading Semantic Validator Model: {model_name}")
        # Load model on CPU/GPU depending on availability, usually reliable default
        self.model = SentenceTransformer(model_name)
        self.judge = LLMJudge()

    async def validate_pair(self, 
                          raw_text: str, 
                          target_text: str, 
                          current_start: float, 
                          last_valid_end: float = None) -> dict:
        """
        Validates if raw_text supports target_text semantically and chronologically.
        Returns: { "status": "GREEN"|"YELLOW"|"RED", "score": float, "reasoning": str, "source": "EMBEDDING"|"LLM" }
        """
        
        # 0. Monotonicity Check (Temporal Logic)
        if last_valid_end is not None:
            # Allow a small tolerance (e.g., 0.5s overlap) if needed, but strict for now
            if current_start < last_valid_end: 
                return { 
                    "status": "RED", 
                    "score": 0.0, 
                    "reasoning": f"Temporal Inconsistency: Starts at {current_start}s before previous ended at {last_valid_end}s.",
                    "source": "TEMPORAL"
                }

        # 1. Embeddings Similarity (Fast Filter)
        # Using run_in_executor to avoid blocking event loop during encoding
        loop = asyncio.get_running_loop()
        embeddings = await loop.run_in_executor(
            None, 
            lambda: self.model.encode([raw_text, target_text], convert_to_tensor=True)
        )
        
        # Calculate cosine similarity
        score = float(util.cos_sim(embeddings[0], embeddings[1])[0][0])
        
        # 2. Threshold Logic
        if score < 0.4:
            return { 
                "status": "RED", 
                "score": score, 
                "reasoning": f"Low Similarity ({score:.2f}) - Context Mismatch",
                "source": "EMBEDDING"
            }
        
        if score > 0.85:
             return { 
                 "status": "GREEN", 
                 "score": score, 
                 "reasoning": f"High Confidence Match ({score:.2f})",
                 "source": "EMBEDDING"
             }

        # 3. LLM Judge (Yellow Zone / Ambiguous)
        logger.info(f"Invoking LLM Judge for ambiguous pair (Score: {score:.2f})")
        judge_result = await self.judge.evaluate(raw_text, target_text)
        
        final_score = judge_result["score"]
        reasoning = judge_result["reasoning"]

        # Mapping: LLM Score -> Status
        # LLM Score 1.0 -> Green
        # LLM Score 0.5 -> Yellow
        # LLM Score 0.0 -> Red
        
        if final_score >= 0.7:
             status = "GREEN"
        elif final_score <= 0.3:
             status = "RED"
        else:
             status = "YELLOW" # True edge case

        return {
            "status": status,
            "score": final_score, 
            "reasoning": f"LLM Audit ({score:.2f} -> {final_score:.2f}): {reasoning}",
            "source": "LLM"
        }
