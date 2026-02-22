import os
import torch
from unsloth import FastLanguageModel
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

def train(
    dataset_path: str,
    val_dataset_path: str,
    output_dir: str,
    max_seq_length: int = 2048,
    load_in_4bit: bool = True
):
    """
    Ejecuta el pipeline de entrenamiento SFT usando Unsloth Llama-3.
    """
    
    # 1. Cargar Modelo Base Optimizado
    model_name = "unsloth/llama-3-8b-Instruct-bnb-4bit"
    
    print(f"--> Loading model: {model_name}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = model_name,
        max_seq_length = max_seq_length,
        dtype = None, # Auto-detect
        load_in_4bit = load_in_4bit,
    )

    # 2. Configurar Adaptadores LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r = 16, # Rank
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj",
                          "gate_proj", "up_proj", "down_proj",],
        lora_alpha = 16,
        lora_dropout = 0, # Unsloth recomienda 0
        bias = "none",
        use_gradient_checkpointing = True, # Ahorro de VRAM
        random_state = 3407,
        use_rslora = False,
        loftq_config = None,
    )

    # 3. Preparar Dataset (Formato Alpaca)
    alpaca_prompt = """### Instruction:
{}

### Input:
{}

### Response:
{}"""

    def formatting_prompts_func(examples):
        instructions = examples["instruction"]
        inputs       = examples["input"]
        outputs      = examples["output"]
        texts = []
        for instruction, input, output in zip(instructions, inputs, outputs):
            text = alpaca_prompt.format(instruction, input, output) + tokenizer.eos_token
            texts.append(text)
        return { "text" : texts }

    print("--> Loading datasets...")
    dataset = load_dataset("json", data_files={"train": dataset_path, "validation": val_dataset_path})
    train_dataset = dataset["train"].map(formatting_prompts_func, batched=True)
    eval_dataset = dataset["validation"].map(formatting_prompts_func, batched=True)

    # 4. Configurar Trainer
    training_args = TrainingArguments(
        per_device_train_batch_size = 2,
        gradient_accumulation_steps = 4,
        warmup_steps = 5,
        max_steps = 60, # Demo: En prod usar num_train_epochs
        learning_rate = 2e-4,
        fp16 = not torch.cuda.is_bf16_supported(),
        bf16 = torch.cuda.is_bf16_supported(),
        logging_steps = 1,
        optim = "adamw_8bit", # Optimizador ligero
        weight_decay = 0.01,
        lr_scheduler_type = "linear",
        seed = 3407,
        output_dir = output_dir,
        report_to = "none", # Desactivar WandB/Tensorboard en serverless
    )

    trainer = SFTTrainer(
        model = model,
        tokenizer = tokenizer,
        train_dataset = train_dataset,
        eval_dataset = eval_dataset,
        dataset_text_field = "text",
        max_seq_length = max_seq_length,
        dataset_num_proc = 2,
        packing = False, # Packing can speed up training for short sequences
        args = training_args,
    )

    # 5. Ejecutar Entrenamiento
    print("--> Starting training...")
    trainer.train()

    # 6. Guardar Adaptadores
    print(f"--> Saving adapters to {output_dir}...")
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    
    return {"status": "completed"}