import runpod
import os
import sys

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from src.inference.llm_engine import LLMEngine
from src.config import settings

# Initialize the engine globally so it loads the model once (Warm Start)
print("--> Initializing LLM Engine...")
# We might need to override settings for RunPod environment if not using .env
# But usually env vars are passed in RunPod dashboard.
engine = LLMEngine()

def handler(event):
    """
    RunPod handler function.
    event: { "input": { "prompt": "...", "mode": "xml", ... } }
    """
    job_input = event.get("input", {})
    
    prompt = job_input.get("prompt")
    mode = job_input.get("mode", "default")
    
    if not prompt:
        return {"error": "No prompt provided in input."}
    
    try:
        # Generate response
        # Note: runpod handler usually returns JSON. 
        # Streaming is supported via generator but let's start with blocking.
        response = engine.generate(prompt, mode=mode)
        return {"output": response}
    
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
