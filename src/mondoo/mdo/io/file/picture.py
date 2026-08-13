from __future__ import annotations

from mondoo.mdo.core.common import (
    Paragraph,
    Figure,
    BaseModelWithBody
)

from .generic import FileDesc

from pathlib import Path
from os import PathLike
from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict
from PIL import Image


class Body:
    def __init__(
        self,
        paragraphs  : Optional[List[Paragraph]] = None,
        figures     : Optional[List[Figure]]    = None,
        total_words : Optional[int]             = None
    ):
        self.paragraphs  = paragraphs  or []
        self.figures     = figures     or []
        self.total_words = total_words or 0

    def to_dict(self) -> Dict:
        return {
            'paragraphs' : [p.to_dict() for p in self.paragraphs],
            'figures'    : [i.to_dict() for i in self.figures]
        }
        
    def update(
        self,
        body : Body
    ) -> None:
        self.paragraphs  += body.paragraphs
        self.figures     += body.figures
        self.total_words += body.total_words    
    

def dump_image_body_to_md(
    body        : Body,
    md_out_path : PathLike[str],
    image_dir   : PathLike[str]
):
    image_dir.mkdir(parents=True, exist_ok=True)
    
    for figures in body.figures:
        figures.export(image_dir)
    
    with open(md_out_path, "w", encoding="utf-8") as f:
        for i, para in enumerate(body.paragraphs):    
            if len(para.page_ids) == 1:
                page_str = str(para.page_ids[0])
            elif len(para.page_ids) > 1:
                page_str = f'{para.page_ids[0]}–{para.page_ids[-1]}'
            else:
                page_str = ''
            
            # Markdown output
            f.write(f"*[Paragraph: {i + 1}; Count: {para.count}; Pages: {page_str}]*\n\n")
            f.write(para.content)
            f.write("\n\n")
    
    print(f"📂  Result cached → {md_out_path}")



class ImageObject(BaseModelWithBody):
    descriptor : FileDesc  = Field(None, description="")
    body       : Body | None = Field(None, description="")