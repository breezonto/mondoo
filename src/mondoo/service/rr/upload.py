from .generic import RespStatus
from pydantic import BaseModel, Field
from typing   import Literal


class ReqCompleteUpload(BaseModel):
    parse_meth      : Literal['text', 'ocr']
    should_cache    : bool = False
    should_offline  : bool = False

    
class RespUploading(BaseModel):
    status               : str
    slice_index          : int
    percent              : float
    client_send_time     : str
    server_recv_time     : str
    transfer_duration    : str
    server_save_duration : str


class RespFileStatus(BaseModel):
    status  : str
    file_id : str   = Field(description="The unique id of that file")
    stage   : str   = Field(description="The stage of that file")