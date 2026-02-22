import json
from typing import List, Dict
import os

class DatasetFormatter:
    """
    Formats aligned data pairs into Alpaca-style JSONL for Unsloth/LoRA training.
    """
    
    SYSTEM_INSTRUCTION = "Formalize the transcription into an OOXML paragraph with appropriate styles."
    
    @staticmethod
    def format_as_alpaca(aligned_pairs: List[Dict], output_path: str):
        """
        Writes aligned pairs to a JSONL file.
        
        Args:
            aligned_pairs: List of dicts with keys 'input' (transcript) and 'output' (xml).
            output_path: Destination file path.
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for pair in aligned_pairs:
                data = {
                    "instruction": pair.get("instruction", DatasetFormatter.SYSTEM_INSTRUCTION),
                    "input": pair.get("input", ""),
                    "output": pair.get("output", "")
                }
                
                # Validation: Ensure content is not empty
                if not data["input"].strip() or not data["output"].strip():
                    continue
                    
                json.dump(data, f, ensure_ascii=False)
                f.write('\n')
        
        print(f"[DatasetFormatter] Wrote {len(aligned_pairs)} samples to {output_path}")

    @staticmethod
    def split_train_val(aligned_pairs: List[Dict], train_ratio: float = 0.9):
        """
        Splits data into train and validation sets.
        """
        # Deterministic split
        split_idx = int(len(aligned_pairs) * train_ratio)
        return aligned_pairs[:split_idx], aligned_pairs[split_idx:]
