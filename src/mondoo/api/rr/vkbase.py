from typing   import List, Optional
from pydantic import BaseModel, Field

class ChunkObject(BaseModel):
    content:     str       = Field(..., description="Text content of the chunk")
    count:       int       = Field(..., description="Number of tokens in the chunk")
    page_idx:    List[int] = Field(..., description="List of page numbers this chunk is from")


class RetrievedDocument(BaseModel):
    id      : str
    score   : float
    source  : str                 = 'unknown'
    count   : int                 = -1
    page    : Optional[List[int]] = None
    start   : Optional[int]       = None
    end     : Optional[int]       = None
    excerpt : str


class ReqStore(BaseModel):
    file_id   :  str
    file_name :  str
    file_type :  str
    # chunks    :  List[ChunkObject]
    

class RespStore(BaseModel):
    status    : str
    message   : str


class ReqRemove(BaseModel):
    file_id      : str
    total_chunks : int


class RespRemove(BaseModel):
    status    : str
    message   : str


class ReqRetrieve(BaseModel):
    query: str = Field(..., description="User query text")
    top_k: int = Field(3,   description="Number of documents to retrieve")
    

class RespRetrieve(BaseModel):
    query   : str
    results : List[RetrievedDocument]
    
    
class RespBuscar(BaseModel):
    query   : str
    results : List[RetrievedDocument]