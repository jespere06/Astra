import os
import json
from openai import AsyncOpenAI

class LLMJudge:
    def __init__(self, model="gpt-4-turbo-preview"):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model

    async def evaluate(self, raw_text: str, target_text: str) -> dict:
        """
        Evaluates if the raw transcription justifies the target summary/acta text.
        Returns: { "score": float, "reasoning": str }
        """
        system_prompt = """You are a Forensic Auditor analyzing legal records.
Your task is to determine if the EVIDENCE (Audio Transcription) semantically supports the CLAIM (Official Record/Acta).
Focus on meaning, not exact wording. The Record is often a summary.

Input:
- EVIDENCE: Raw text from audio.
- CLAIM: Text from the official document.

Output JSON with:
- score: Float 0.0 to 1.0. 
  - 1.0: Full support (Claim is fully derived from Evidence).
  - 0.5: Partial support (Some key details match, others missing or different).
  - 0.0: No support (Hallucination or completely different topic).
- reasoning: Short explanation (max 1 sentence).
"""

        user_prompt = f"EVIDENCE: {raw_text}\nCLAIM: {target_text}"

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return {
                "score": float(result.get("score", 0.0)),
                "reasoning": result.get("reasoning", "No reasoning provided")
            }
        except Exception as e:
            print(f"LLM Judge Error: {e}")
            return {"score": 0.0, "reasoning": "LLM Error"}
