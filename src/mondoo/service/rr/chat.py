from pydantic import BaseModel, Field
from typing   import List, Dict, Optional, Literal
from enum     import Enum


class Role(str, Enum):
    SYSTEM    = 'system'
    USER      = 'user'
    ASSISTANT = 'assistant'
    TOOL      = 'tool'


class Message(BaseModel):
    role:    Role
    content: str


class Choice(BaseModel):
    index         : int
    message       : Message
    logprobs      : Optional[Dict] = None
    finish_reason : Optional[str]  = None


class Usage(BaseModel):
    prompt_tokens            : Optional[int]   = None
    completion_tokens        : Optional[int]   = None
    total_tokens             : Optional[int]   = None
    token_generation_speed   : Optional[float] = None
    prompt_tokens_details    : Optional[Dict]  = None
    prompt_cache_hit_tokens  : Optional[int]   = 0
    prompt_cache_miss_tokens : Optional[int]   = 0


class ReqChatOptions(BaseModel):
    max_tokens         : Optional[int]       = Field(100,   description="Maximum tokens to generate")
    temperature        : Optional[float]     = Field(1.0,   description="Randomness in output")
    top_p              : Optional[float]     = Field(1.0,   description="Nucleus sampling probability")
    top_k              : Optional[int]       = Field(50,    description="Top-k sampling")
    repetition_penalty : Optional[float]     = Field(0.0,   description="Repetition penalty")
    stop_sequences     : Optional[List[str]] = Field(None,  description="Stop generation if any sequence appears")
    stream             : Optional[bool]      = Field(False, description="Whether to stream the output")
    chunk_size         : Optional[int]       = Field(5,     description="Words per chunk for local streaming")
    system_prompt      : Optional[str]       = Field("",    description="Optional system prompt / context")


class ReqChatCompletion(BaseModel):
    model_type : Literal['local', 'remote']
    messages   : List[Message]
    memory_id  : Optional[str]            = Field("", description="Should incetive the internal memory?")
    options    : Optional[ReqChatOptions] = ReqChatOptions()
    
          
class RespChatCompletionNoStream(BaseModel):
    id                 : str
    object             : str
    created            : int
    model_type         : str
    choices            : List[Choice]
    usage              : Optional[Usage] = None
    system_fingerprint : Optional[str]   = None 