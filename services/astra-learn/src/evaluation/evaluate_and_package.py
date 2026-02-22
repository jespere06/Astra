import torch
from unsloth import FastLanguageModel
from transformers import TextStreamer

def evaluate(
    adapter_path: str = "astra-lora-adapter",
    base_model_name: str = "unsloth/llama-3-8b-Instruct-bnb-4bit",
    max_seq_length: int = 2048,
):
    """
    Loads a trained adapter and runs inference for validation.
    """
    
    print(f"Loading adapter from {adapter_path}...")
    
    # 1. Load Model + Adapter
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = adapter_path, # Load from local adapter folder
        max_seq_length = max_seq_length,
        dtype = None,
        load_in_4bit = True,
    )
    
    FastLanguageModel.for_inference(model) # Enable native inference optimization

    # 2. Prepare Inference Prompt
    alpaca_prompt = """### Instruction:
{}

### Input:
{}

### Response:
{}"""

    instruction = "Actúa como un redactor de actas y formaliza el siguiente texto transcrito."
    input_text = "el concejal perez eh dice que no esta de acuerdo con la plata del puente"
    
    inputs = tokenizer(
        [
            alpaca_prompt.format(
                instruction,
                input_text,
                "", # Generation output
            )
        ], return_tensors = "pt").to("cuda")

    # 3. Generate
    print("\nCorrecting: ", input_text)
    print("-" * 40)
    
    text_streamer = TextStreamer(tokenizer)
    _ = model.generate(**inputs, streamer = text_streamer, max_new_tokens = 128)
    
    # 4. Packaging Strategy (Placeholder)
    # If we need to merge to GGUF:
    # model.save_pretrained_gguf("model", tokenizer, quantization_method = "q4_k_m")

if __name__ == "__main__":
    evaluate()
