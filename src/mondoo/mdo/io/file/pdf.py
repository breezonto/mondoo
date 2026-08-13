from __future__ import annotations

from mondoo.mdo.core.common import (
    Paragraph,
    Figure,
    VectorGraphic,
    BaseModelWithBody,
    Chunk
)

from .generic import FileDesc

from itertools   import groupby
from collections import defaultdict
from pathlib     import Path
from os          import PathLike
from typing      import Optional, List, Dict
from pydantic    import BaseModel, Field, ConfigDict

import json
import re
import fitz   
import os
import logging


logger = logging.getLogger(__name__)


class Body:
    def __init__(
        self,
        paragraphs     : Optional[List[Paragraph]]     = None,
        figures        : Optional[List[Figure]]        = None,
        vgraphics      : Optional[List[VectorGraphic]] = None,
        total_words    : int                 = 0
    ):
        self.paragraphs  = paragraphs or []
        self.figures     = figures    or []
        self.vgraphics   = vgraphics  or []
        self.total_words = total_words
        
    def to_dict(self) -> Dict:
        return {
            "paragraphs"     : [p.to_dict() for p in self.paragraphs],
            "figures"        : [i.to_dict() for i in self.figures],
            "vector_graphics": [v.to_dict() for v in self.vgraphics]
        }
        
    def _sort_by_page_ids_(self):
        def _key_(elem):
            return elem.page_ids[0]
            
        self.paragraphs.sort(key=_key_)
        self.figures.sort(key=_key_)
        self.vgraphics.sort(key=_key_)
    
    def update(
        self,
        body : Body
    ) -> None:
        self.paragraphs    += body.paragraphs
        self.figures       += body.figures
        self.vgraphics     += body.vgraphics
        self.total_words   += body.total_words
        self._sort_by_page_ids_()
    

class PDFObject(BaseModelWithBody):
    descriptor     : FileDesc          = Field(None, description="")
    total_pages    : Optional[int]       = Field(0, ge=0, description="")
    cover_pages    : Optional[List[int]] = Field([], description="")
    category_pages : Optional[List[int]] = Field([], description="")
    pages_method   : List[str]           = Field([], description="")
    body           : Body | None         = Field(None, description="")
    

def _is_horizontal_dir_(dir_tuple, tol=1e-5):
    """
    Check if the text line direction is horizontal (1.0, 0.0) within a tolerance.
    """
    if dir_tuple is None:
        return False
    dx, dy = dir_tuple
    return abs(dx - 1.0) < tol and abs(dy - 0.0) < tol


def _collect_lines_(pages):
    lines = []
    min_width_ratio = 0.1
    for page in pages:
        page_width = page['width']
        
        for block in page.get('blocks', []):
            if block.get('type') != 0:  # only text blocks
                continue

            for line in block.get('lines', []):
                # Filter 1: skip lines with only whitespace
                line_text = "".join(span.get('text', "") for span in line.get('spans', []))
                
                if not line_text.strip() or not _is_horizontal_dir_(line.get('dir')):
                    continue
                
                # Filter 3: skip lines too short relative to page width
                x0, y0, x1, y1 = line["bbox"]
                line_width = x1 - x0
                if line_width / page_width < min_width_ratio:
                    continue
                
                line_copy = dict(line)
                line_copy["page_idx"] = page['page_number']
                lines.append(line_copy)

    return lines


def _sort_document_lines_(lines, y_tol=3):
    def key(line):
        x0, y0, x1, y1 = line["bbox"]
        # three sorted keys: page index, y-axis value (y0/y_tol important !), x-axis value
        return (line["page_idx"], round(y0 / y_tol), x0)
    return sorted(lines, key=key)


def _extract_blocks_from_pdf_(
    doc,
    skipped_pages
):
    pages_out = []
    extracted_images = {}  # xref -> image bytes

    figures = []
    vgraphics = []

    for page_id, page in enumerate(doc, start=1):
        if page_id in skipped_pages:
            continue

        page_out = {
            "page_number"  : page_id,
            "width"        : page.rect.width,
            "height"       : page.rect.height,
            "blocks"       : []
        }

        # -------------------------
        # PASS 1: extract images (IN MEMORY)
        # -------------------------
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            if xref in extracted_images:
                continue

            img_dict = doc.extract_image(xref)

            image_bytes = img_dict["image"]
            image_ext   = img_dict["ext"]
            width       = img_dict.get("width")
            height      = img_dict.get("height")

            extracted_images[xref] = image_bytes

            figures.append(
                Figure(
                    image_bytes=image_bytes,
                    image_ext=image_ext,
                    width=width,
                    height=height,
                    page_ids=[page_id],
                    index=img_index
                )
            )

        # -------------------------
        # PASS 2: walk layout blocks
        # -------------------------
        page_dict = page.get_text("dict")

        for block_index, block in enumerate(page_dict.get("blocks", [])):
            block_type = block.get("type")
            bbox = block.get("bbox")

            # TEXT
            if block_type == 0:
                page_out["blocks"].append(block)
                continue

            # IMAGE (layout only)
            if block_type == 1:
                page_out["blocks"].append({
                    "type": 1,
                    "bbox": bbox,
                    "note": "image block (stored in memory)"
                })
                continue

            # VECTOR / DRAWING (IN MEMORY)
            if block_type == 2:
                clip = fitz.Rect(bbox)
                pix = page.get_pixmap(clip=clip, dpi=300)

                vgraphics.append(
                    VectorGraphic(
                        pixmap=pix,
                        page_ids=[page_id],
                        index=block_index
                    )
                )

                page_out["blocks"].append({
                    "type": 2,
                    "bbox": bbox,
                    "note": "vector graphic stored in memory"
                })
                continue

        pages_out.append(page_out)

    return pages_out, figures, vgraphics



def _group_document_lines_into_paragraphs_(
    lines,
    tail_difference_thres=0.1,
    head_difference_thres=0.1
):
    paragraphs = []
    curr_para = []

    if not lines:
        return paragraphs
    
    # avg_line_most_left  = min(line['bbox'][0] for line in lines)
    # avg_line_most_right = max(line['bbox'][2] for line in lines)
    # frame_width         = avg_line_most_right - avg_line_most_left
    
    lines_in_pages = defaultdict(list)
    
    for line in lines:
        lines_in_pages[line['page_idx']].append(line)
    
    for page_idx, lines_in_page in lines_in_pages.items():
        avg_line_most_left  = min(line['bbox'][0] for line in lines_in_page)
        avg_line_most_right = max(line['bbox'][2] for line in lines_in_page)
        frame_width         = avg_line_most_right - avg_line_most_left
        for j, line in enumerate(lines_in_page):
            x0, y0, x1, y1 = line['bbox']
            tail_diff_ratio = (avg_line_most_right - x1) / frame_width
            head_diff_ratio = (x0 - avg_line_most_left)  / frame_width
        
            is_new_para = tail_diff_ratio > tail_difference_thres
            curr_para.append(line)
            
            if is_new_para:
                paragraphs.append(curr_para)
                curr_para = []

    if curr_para:
        paragraphs.append(curr_para)
    
    return paragraphs


def count_pages(pdf_path: str) -> int:
    doc = fitz.open(pdf_path)
    total_pages = doc.page_count
    return total_pages


def extarct_pdf_body(
    pdf_path      : PathLike[str], 
    intermediate_path    : Optional[PathLike[str] | None] = None,
    skipped_pages : List[int] = []
) -> Body:
    
    pdf_path = Path(pdf_path)

    doc = fitz.open(pdf_path)
    pages, figures, vgraphics = _extract_blocks_from_pdf_(
        doc,
        skipped_pages
    )
    
    lines = _collect_lines_(pages)
    lines = _sort_document_lines_(lines)
    native_paragraphs = _group_document_lines_into_paragraphs_(lines)

    if type == "zh":
        para_to_text = lambda para: "".join(
            span["text"] for line in para for span in line["spans"]
        ).strip()
    else:
        para_to_text = lambda para: re.sub(
            r"\s+",
            "",
            "".join(span["text"] for line in para for span in line["spans"])
        )

    paragraphs = []
    total_count = 0
    for i, para in enumerate(native_paragraphs):
        text = para_to_text(para)
        count = len(text)
        page_ids = sorted({line["page_idx"] for line in para})
        paragraphs.append(
            Paragraph(
                page_ids=page_ids,
                content=text,
                count=count
            )
        )
        total_count += count
    
    if intermediate_path is not None:
        intermediate_path = Path(intermediate_path)        
        parent = intermediate_path.parent        
        if parent.exists():
            with open(intermediate_path, "w", encoding="utf-8") as f:
                json.dump(pages, f, ensure_ascii=False, indent=2)
        else:
            raise ValueError("Parent directory of the specified path " 
                             + f"[{str(intermediate_path)}] doesn't exist")        
    
    return Body(
        paragraphs  = paragraphs,
        figures     = figures,
        vgraphics   = vgraphics,
        total_words = total_count
    )


MIN_CHUNK_SIZE      = 300
SOFT_MAX_CHUNK_SIZE = 500


def _make_unique_page_number_(page_number):
    pn_set = set(page_number)
    page_number_passage = sorted(list(pn_set))
    
    return page_number_passage


def group_paragraphs_to_chunks(
    paragraphs : List[Paragraph]
):
    all_chunks = []
    
    curr_chunk_content = ""
    curr_chunk_count = 0
    curr_chunk_pages = []
    for paragraph in paragraphs:
        count   = paragraph.count
        if count <= 0: continue
        content = paragraph.content
        pages   = paragraph.page_ids

        if curr_chunk_count + count < SOFT_MAX_CHUNK_SIZE:
            curr_chunk_content += content
            curr_chunk_count   += count
            curr_chunk_pages   += pages
        else:
            if curr_chunk_count > 0 and len(curr_chunk_pages) > 0:
                curr_chunk_pages = _make_unique_page_number_(curr_chunk_pages)
                all_chunks.append(
                    Chunk(
                        content  = curr_chunk_content,
                        page_idx = curr_chunk_pages,
                        count    = curr_chunk_count
                    )
                )
            if count < SOFT_MAX_CHUNK_SIZE:
                curr_chunk_content = content
                curr_chunk_count   = count
                curr_chunk_pages   = pages
            else:
                all_chunks.append(
                    Chunk(
                        content  = content,
                        page_idx = pages,
                        count    = count
                    )
                )
                curr_chunk_content = ""
                curr_chunk_count = 0
                curr_chunk_pages = []
    
    all_chunks.append(
        Chunk(
            content  = curr_chunk_content,
            page_idx = curr_chunk_pages,
            count    = curr_chunk_count
        )
    )
    
    return all_chunks

    
def dump_pdf_body_to_md(
    body        : Body,
    md_out_path : PathLike[str],
    image_dir   : PathLike[str],
    vector_dir  : PathLike[str]
):
            
    image_dir.mkdir(parents=True, exist_ok=True)
    vector_dir.mkdir(parents=True, exist_ok=True)
    
    for figures in body.figures:
        figures.export(image_dir)
    
    for vgraphic in body.vgraphics:
        vgraphic.export(vector_dir)
    
    with open(md_out_path, 'w', encoding='utf-8') as f:
        for i, para in enumerate(body.paragraphs):    
            if len(para.page_ids) == 1:
                page_str = str(para.page_ids[0])
            else:
                page_str = f"{para.page_ids[0]}–{para.page_ids[-1]}"
        
            # Markdown output
            f.write(f"*[Paragraph: {i + 1}; Count: {para.count}; Pages: {page_str}]*\n\n")
            f.write(para.content)
            f.write('\n\n')
    
    print(f"📂  Result cached → {md_out_path}")
    

def convert_pdf_to_images(
    pdf_path : str, 
    out_path : str
):
    doc = fitz.open(pdf_path)
    
    os.makedirs(out_path, exist_ok=True)

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)

        # 2x resolution scaling
        mat = fitz.Matrix(1, 1)

        pix = page.get_pixmap(matrix=mat)

        output = os.path.join(out_path, f'page_{page_num+1:04d}.png')
        pix.save(output)

    logger.info(f"Saved {len(doc)} pages of {pdf_path} to {out_path}")