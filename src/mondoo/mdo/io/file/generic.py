from enum     import Enum
from pydantic import BaseModel, Field
from os       import PathLike
from typing   import Optional, Dict

import uuid
import json

class FileStage(str, Enum):
    DELETED   = 'deleted'
    UPLOADING = 'uploading'
    UPLOADED  = 'uploaded'
    CACHED    = 'cached'
    STORED    = 'stored'
    STALE     = 'stale'


class FileDesc(BaseModel):
    file_id     : Optional[str] = Field(f'auto-{uuid.uuid4().hex}', description="")
    source_path : Optional[str] = Field('', description  = "The path of the saved source (original) document")
    target_path : Optional[str] = Field('', description  = "The path of the saved parsed (cached) document")
    stem        : Optional[str] = Field('', description  = "The filename (extension trimmed) of document")
    ext         : Optional[str] = Field('', descriptrion = "The extension (file type) of document")
    size        : Optional[int] = Field(0,  description  = "The size in bytes of document")


class FileRecord(BaseModel):
    desc           : FileDesc
    stage          : FileStage
    curr_slice     : int
    total_slices   : int
    total_chunks   : int
    
    @classmethod
    def create(cls,
        id           : str,
        source_path  : PathLike[str],
        target_path  : PathLike[str],
        stem         : str,
        ext          : str,
        size         : int,
        stage        : str,
        curr_slice   : int,
        total_slices : int,
        total_chunks : int
    ):
        desc = FileDesc(
            file_id     = id,
            source_path = source_path,
            target_path = target_path,
            stem        = stem,
            ext         = ext,
            size        = size
        )
        
        return FileRecord(
            desc         = desc,
            stage        = stage,
            curr_slice   = curr_slice,
            total_slices = total_slices,
            total_chunks = total_chunks
        )
    
    
    def model_dump(self):
        model                 = self.desc.model_dump()
        model['stage']        = self.stage
        model['curr_slice']   = self.curr_slice
        model['total_slices'] = self.total_slices
        model['total_chunks'] = self.total_chunks
        return model
    
    @property
    def view(self):
        return {
            'file_id'   : self.desc.file_id,
            'filename'  : self.desc.stem,
            'type'      : self.desc.ext,
            'size'      : self.desc.size,
            'stage'     : self.stage,
            'num_chunk' : self.total_chunks
        }
        
    @property
    def user_view(self):
        return {
            'filename'  : self.desc.stem,
            'type'      : self.desc.ext,
            'size'      : self.desc.size,
            'stage'     : self.stage,
            'num_chunk' : self.total_chunks
        }