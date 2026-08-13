import torch
from typing import Union
from transformers import PreTrainedModel, PreTrainedTokenizer, AutoModelForCausalLM, AutoTokenizer

def model_info(model: Union[PreTrainedModel, torch.nn.Module], name: str = None):
    """
    Print a formatted summary of a Hugging Face Transformer model.
    Includes dtype, device, parameter stats, memory usage, and basic config info.
    """
    print("=" * 60)
    if name:
        print(f" Model Summary: {name}")
    else:
        print(f" Model Summary")
    print("=" * 60)

    # --- Basic Type & Device Info ---
    try:
        dtype = next(model.parameters()).dtype
        device = next(model.parameters()).device
    except StopIteration:
        dtype, device = "N/A", "N/A"

    print(f"• Model class:      {model.__class__.__name__}")
    print(f"• Data type:        {dtype}")
    print(f"• Device:           {device}")

    # --- Parameter Counts ---
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    dtype_size = torch.finfo(next(model.parameters()).dtype).bits / 8
    memory_gb = total_params * dtype_size / (1024 ** 3)

    print(f"• Total parameters: {total_params:,}")
    print(f"• Trainable params: {trainable_params:,}")
    print(f"• Est. weight size: {memory_gb:.2f} GB")

    # --- Config Info (if available) ---
    if hasattr(model, "config"):
        cfg = model.config
        print("-" * 60)
        print(" Config Summary")
        print("-" * 60)
        attrs = [
            "model_type", "vocab_size", "hidden_size",
            "num_hidden_layers", "num_attention_heads",
            "max_position_embeddings", "eos_token_id"
        ]
        for attr in attrs:
            if hasattr(cfg, attr):
                print(f"• {attr:22s}: {getattr(cfg, attr)}")
    else:
        print("(No model.config found)")

    print("=" * 60)
    print()

def tokenizer_info(tokenizer: PreTrainedTokenizer, name: str = None):
    """
    Print a formatted summary of a Hugging Face tokenizer.
    Includes vocab size, special tokens, and some configuration info.
    """
    print("=" * 60)
    if name:
        print(f" Tokenizer Summary: {name}")
    else:
        print(" Tokenizer Summary")
    print("=" * 60)

    print(f"• Tokenizer class:  {tokenizer.__class__.__name__}")
    print(f"• Vocabulary size:  {tokenizer.vocab_size}")
    print(f"• Model max length: {tokenizer.model_max_length}")
    print(f"• Padding side:     {tokenizer.padding_side}")
    print(f"• Truncation side:  {getattr(tokenizer, 'truncation_side', 'N/A')}")

    print("-" * 60)
    print(" Special Tokens")
    print("-" * 60)
    special_tokens = [
        "bos_token", "eos_token", "unk_token",
        "pad_token", "sep_token", "cls_token",
        "mask_token"
    ]
    for token in special_tokens:
        val = getattr(tokenizer, token, None)
        if val:
            print(f"• {token:12s}: {val} (id={tokenizer.convert_tokens_to_ids(val)})")
    print("=" * 60)
    print()
    
def model_info_from_path(model_path: str, name: str = None):
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        device_map="auto",
        torch_dtype="auto",
    )
    model_info(model, name)
    
def tokenizer_info_from_path(tokenizer_path: str, name: str = None):
    tokenizer = AutoTokenizer.from_pretrained(tokenizer_path, trust_remote_code=True)
    tokenizer_info(tokenizer, name)


if __name__ == "__main__":
    model_path = "/home/breeze/workspace/models/qwen-family/2.5-1.5B-instruct"
    tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        device_map="auto",
        torch_dtype="auto",
    )
    tokenizer_info(tokenizer, name="Qwen2.5-1.5B-Instruct")
    model_info(model, name="Qwen2.5-1.5B-Instruct")