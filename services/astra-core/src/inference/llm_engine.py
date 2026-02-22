import torch
import json
from threading import Thread
from transformers import TextIteratorStreamer
from src.config import get_settings
from src.inference.model_loader import ModelLoader

settings = get_settings()

class LLMEngine:
    XML_PROMPT_TEMPLATE = """### Instruction:
Formalize the transcription into an OOXML paragraph with appropriate styles.

### Input:
{}

### Response:
"""

    DEFAULT_PROMPT_TEMPLATE = """### Instruction:
Actúa como un redactor de actas y formaliza el siguiente texto transcrito.

### Input:
{}

### Response:
"""

    def __init__(self):
        self.loader = ModelLoader()
        # Ensure model is loaded (lazy loading triggered by __new__)
        self.model = self.loader.model
        self.tokenizer = self.loader.tokenizer

    def _build_prompt(self, user_input: str, mode: str = "default") -> str:
        """
        Constructs the Alpaca-style prompt for the model.
        """
        if mode == "xml":
            return self.XML_PROMPT_TEMPLATE.format(user_input)
        return self.DEFAULT_PROMPT_TEMPLATE.format(user_input)

    def generate_stream(self, user_input: str, mode: str = "default"):
        """
        Generator function that yields SSE events.
        """
        prompt = self._build_prompt(user_input, mode)
        inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")

        streamer = TextIteratorStreamer(
            self.tokenizer, 
            skip_prompt=True,
            skip_special_tokens=True
        )

        generation_kwargs = dict(
            inputs, 
            streamer=streamer, 
            max_new_tokens=settings.MAX_NEW_TOKENS,
            temperature=settings.TEMPERATURE,
            do_sample=True,
            pad_token_id=self.tokenizer.eos_token_id
        )

        # Run generation in a separate thread to unblock the streamer
        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        for new_text in streamer:
            # Yield SSE format: data: {"delta": "word"}
            yield f"data: {json.dumps({'delta': new_text})}\n\n"
        
        # Signal End of Stream
        yield "data: [DONE]\n\n"

    def _sanitize_xml_output(self, text: str) -> str:
        """
        Strips markdown code fences (```xml ... ```) from the output.
        """
        text = text.strip()
        if text.startswith("```xml"):
            text = text[6:]
        elif text.startswith("```"):
            text = text[3:]
        
        if text.endswith("```"):
            text = text[:-3]
            
        return text.strip()

    def generate(self, user_input: str, mode: str = "default") -> str:
        """
        Non-streaming generation.
        """
        prompt = self._build_prompt(user_input, mode)
        inputs = self.tokenizer(prompt, return_tensors="pt").to("cuda")

        outputs = self.model.generate(
            **inputs, 
            max_new_tokens=settings.MAX_NEW_TOKENS,
            temperature=settings.TEMPERATURE
        )
        
        # Decode only the new tokens
        full_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Extract response part (simple parsing)
        response_text = full_text
        if "### Response:" in full_text:
            response_text = full_text.split("### Response:")[-1].strip()
        
        if mode == "xml":
            return self._sanitize_xml_output(response_text)
            
        return response_text
