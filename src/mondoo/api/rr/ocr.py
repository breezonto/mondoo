from .generic import RespStatus

from pydantic import BaseModel, Field

class ReqRecognize(BaseModel):
    file_path      : str
    should_offline : bool = True
    

class RespRecognize(BaseModel):
    status         : RespStatus
    name           : str
    results        : list[str]