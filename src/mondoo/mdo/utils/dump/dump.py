from typing import Union
from transformers import PreTrainedModel, PreTrainedTokenizer
import torch

from .info import model_info as _model_info, tokenizer_info as _tokenizer_info
from .info import model_info_from_path as _model_info_from_path
from .info import tokenizer_info_from_path as _tokenizer_info_from_path

class Dump:
    @staticmethod
    def model_info(model: Union[PreTrainedModel, torch.nn.Module, str], name: str = None):
        if isinstance(model, str):
            return _model_info_from_path(model, name)
        return _model_info(model, name)
    
    @staticmethod
    def tokenizer_info(tokenizer: Union[PreTrainedModel, torch.nn.Module, str], name: str = None):
        if isinstance(tokenizer, str):
            return _tokenizer_info_from_path(tokenizer, name)
        return _tokenizer_info(tokenizer, name)
    
    @staticmethod
    def state_dict(path: str, show_values: bool = False, max_values: int = 5):
        from .state import inspect_state_dict
        if path.endswith(".safetensors"):
            from .state import inspect_state_dict_safe
            inspect_state_dict_safe(path, show_values, max_values)
        elif path.endswith(".pt") or path.endswith(".pth"):
            inspect_state_dict(path, show_values, max_values)
        else:
            raise ValueError("Unsupported file format. Use .pt, .pth, or .safetensors")

    @staticmethod
    def trace_model(model: torch.nn.Module, input, device: str = "cuda"):
        from .state import trace
        trace(model, input)
        
    @staticmethod
    def summarize_model(model: torch.nn.Module):
        from .state import summarize
        summarize(model)