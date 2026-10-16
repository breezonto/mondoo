from pydantic import BaseModel, Field
from typing   import List, Optional


class ChunkObject(BaseModel):
    content  : str       = Field(..., description="Text content of the chunk")
    count    : int       = Field(..., description="Number of tokens in the chunk")
    page_idx : List[int] = Field(..., description="List of page numbers this chunk is from")


class StoreRequest(BaseModel):
    file_id   : str
    file_name : str
    file_type : str
    chunks    : List[ChunkObject]
    

class RetrieveRequest(BaseModel):
    query : str = Field(..., description="User query text")
    top_k : int = Field(3,   description="Number of documents to retrieve")
    

class RetrievedDocument(BaseModel):
    id      : str
    score   : float
    source  : str                 = "Unknown"
    page    : Optional[List[int]] = None
    start   : Optional[int]       = None
    end     : Optional[int]       = None
    excerpt : str

    
class RetrieveResponse(BaseModel):
    query   : str
    results : List[RetrievedDocument]