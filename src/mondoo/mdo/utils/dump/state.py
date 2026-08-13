from safetensors import safe_open
import numpy as np
import argparse
import json
import torch

def inspect_state_dict_safe(path, show_values=False, max_values=5):
    """
    Print the state dict of a safetensors model in a formatted way.

    Args:
        path (str): Path to .safetensors file
        show_values (bool): Whether to display a few tensor values
        max_values (int): How many values to show per tensor if show_values=True
    """
    print(f"\nInspecting: {path}\n{'=' * 80}")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    with safe_open(path, framework="pt", device=device) as f:
        keys = f.keys()
        print(f"Total tensors: {len(keys)}\n")
        print(f"key{'-'*60} shape {'-'*25} dtype {'-'*10}")
        for key in keys:
            tensor = f.get_tensor(key)
            print(f"{key:<60} | {str(tuple(tensor.shape)):<25} | {str(tensor.dtype):<10} | ", end="")

            if show_values:
                arr = tensor.flatten()
                preview = arr[:max_values].tolist()
                print(f"   values={json.dumps(preview)}")
        print(f"\n{'=' * 98}")

from torch import nn

def _inspect_tensor_dict(d, prefix="", show_values=False, max_values=3):
    for key, value in d.items():
        full_key = f"{prefix}.{key}" if prefix else key

        if isinstance(value, torch.Tensor):
            shape = tuple(value.shape)
            dtype = str(value.dtype)
            print(f"{full_key:<80} | {str(shape):<25} | {dtype:<10} | ", end="")
            if show_values:
                preview = value.flatten()[:max_values].tolist()
                print(f"values={json.dumps(preview)}")
            else:
                print()
        elif isinstance(value, dict):
            # recursively inspect nested dict
            _inspect_tensor_dict(value, prefix=full_key, show_values=show_values, max_values=max_values)
        else:
            print(f"{full_key:<80} | {'-':<25} | {str(type(value)):<10} | Not a tensor")
            
def inspect_state_dict(path: str, show_values: bool = False, max_values: int = 5):
    """
    Print the state dict of a PyTorch model in a formatted way.

    Args:
        path (str): Path to .pt or .pth file
        show_values (bool): Whether to display a few tensor values
        max_values (int): How many values to show per tensor if show_values=True
    """
    device = "cuda" if torch.cuda.is_available() else "cpu"
    checkpoint = torch.load(path, map_location=device or "cpu")

    # If checkpoint wraps the model under "model" or "state_dict"
    if "model" in checkpoint:
        state_dict = checkpoint["model"]
    elif "state_dict" in checkpoint:
        state_dict = checkpoint["state_dict"]
    else:
        state_dict = checkpoint

    print(f"Total top-level keys: {len(state_dict)}\n")
    print(f"{'key':<80} | {'shape':<25} | {'dtype':<10}")
    _inspect_tensor_dict(state_dict, show_values=show_values, max_values=max_values)
    print(f"\n{'='*98}")

def _register_hooks(model, input_tensor):
    """
    Recursively register hooks to capture input/output shapes of all modules.
    """
    info = []

    def hook_fn(module, inputs, outputs):
        # in_shape = tuple(inputs[0].shape) if isinstance(inputs, tuple) else ()
        if isinstance(inputs, tuple) and len(inputs) > 0 and hasattr(inputs[0], "shape"):
            in_shape = tuple(inputs[0].shape)
        else:
            in_shape = ()
        
        if isinstance(outputs, (tuple, list)):
            out_shape = [tuple(o.shape) for o in outputs if hasattr(o, 'shape')]
        elif hasattr(outputs, 'shape'):
            out_shape = tuple(outputs.shape)
        else:
            out_shape = str(type(outputs))

        params = sum(p.numel() for p in module.parameters() if p.requires_grad)

        info.append({
            'type': module.__class__.__name__,
            'name': getattr(module, '_name', None),
            'in': in_shape,
            'out': out_shape,
            'params': params
        })

    # assign readable names for modules
    for name, module in model.named_modules():
        module._name = name
        # module.register_forward_pre_hook(hook_fn)
        module.register_forward_hook(hook_fn)

    # Forward pass to trigger hooks
    if isinstance(input_tensor, dict):
        _ = model(**input_tensor)
    elif isinstance(input_tensor, (list, tuple)):
        _ = model(*input_tensor)
    else:
        _ = model(input_tensor)

    return info


def trace(model, input_tensor):
    print(f"Inspecting model: {model.__class__.__name__}")
    print("=" * 100)
    info = _register_hooks(model, input_tensor)

    for item in info:
        name = item["name"]
        t = item["type"]
        ins = str(item["in"])
        outs = str(item["out"])
        params = item["params"]
        print(f"name: {name:<50} | {t:<28} | in: {ins:<20} | out: {outs:<25} | params: {params}")

def summarize(module: nn.Module, depth=0, show_params=True):
    cls_name = module.__class__.__name__
    name = getattr(module, '_name', '')
    # Count parameters
    param_count = sum(p.numel() for p in module.parameters() if p.requires_grad)
    
    # Show module shape info if possible
    shape_info = ""
    if isinstance(module, nn.Linear):
        shape_info = f"(in_features={module.in_features}, out_features={module.out_features}, bias={module.bias is not None})"
    elif isinstance(module, nn.Embedding):
        shape_info = f"({module.num_embeddings}, {module.embedding_dim})"
    elif hasattr(module, 'weight') and hasattr(module.weight, 'shape'):
        shape_info = str(tuple(module.weight.shape))
    
    # Print module info
    print(f"{'    ' * depth}({name}: {cls_name}) {shape_info}" + (f" | params: {param_count}" if show_params else ""))

    # Recurse into children
    for name, child in module.named_children():
        child._name = name  # assign name for better readability
        summarize(child, depth + 1, show_params=show_params)