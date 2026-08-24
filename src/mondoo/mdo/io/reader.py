from ..core.object.document import (
    upload_slices_to_ocr, 
    complete_upload_to_ocr,
    predict_in_structure, 
    group_image_detection_to_passages_json
)

from .parser.doc import ( 
    DOCXObject, Body as DOCXBody,
    extract_docx_body, 
    dump_docx_body_to_md,
)

from .parser.picture import ( 
    ImageObject, Body as ImageBody,
    dump_image_body_to_md
)

from .parser.pdf import (
    Paragraph, PDFObject, Body as PDFBody,
    extarct_pdf_body, dump_pdf_body_to_md, count_pages,
    group_paragraphs_to_chunks
)

from ..utils.warn      import WarnNotImplemented
from ..engine.manager.file_descriptor   import FDManager
from ..io.parser.generic import FileDesc

from os      import PathLike
from pathlib import Path
from typing  import List, Optional
from abc     import ABC, abstractmethod

import uuid
import json
import os
import uuid


class classproperty:
    def __init__(self, fget):
        self.fget = fget

    def __get__(self, obj, cls):
        return self.fget(cls)

    
class IReader(ABC):
    @classmethod
    @abstractmethod
    def read(
        cls,
        path              : PathLike[str],
        meth_names        : Optional[List[str] | str],
        intermediate_path : PathLike[str],
        **kwargs
    ) -> any:
        WarnNotImplemented(func_name='read', cls_name=cls.__name__)
    
    @classmethod
    def method_exists(
        cls, 
        method_name: str
    ) -> bool:
        return method_name in cls.methods
    
    @classmethod
    def set_descriptor(
        cls,
        path       : PathLike[str],
        cache_path : Optional[PathLike[str]] = None,
        file_id    : Optional[str]           = None 
    ):
        ipath = Path(path)
        if not ipath.is_file():
            raise ValueError(f"{path} is not a valid path to file")
        
        if file_id is None:
            file_id   = f'user-{uuid.uuid4().hex}'
        
        file_stem = ipath.stem
        file_ext  = ipath.suffix.split('.')[1]
        file_size = ipath.stat().st_size
        
        descriptor = FileDesc(
            file_id          = file_id,
            source_path = path,
            target_path = cache_path,
            stem        = file_stem,
            ext         = file_ext,
            size        = file_size
        )
        
        return descriptor
    
    @classmethod
    def _normalize_methods_(
        cls,
        meth_names: Optional[List[str] | str]
    ):
        '''
        Normalize the methods, 
        i.e remove the duplicated method names and validate they are accepted by current Reader
        
        Args:
            meth_names (List[str]): input method names
        '''
        meth_names = [meth_names] if type(meth_names) == str else meth_names
        return [meth_name for meth_name in meth_names if cls.method_exists(meth_name)]
            
    @classmethod
    def _text_based_extraction_(
        cls, 
        path              : PathLike[str],
        intermediate_path : PathLike[str],
        **kwargs
    ):
        WarnNotImplemented('_text_based_extraction_', cls.__name__)
    
    @classmethod
    def _ocr_based_extraction_(
        cls, 
        path              : PathLike[str],
        intermediate_path : PathLike[str],
        **kwargs
    ):
        WarnNotImplemented('_ocr_based_extraction_', cls.__name__)
    
    
    @classmethod
    def _dump_from_from_annotation_(
        cls, 
        path : PathLike[str]
    ):
        WarnNotImplemented('_dump_from_from_annotation_', cls.__name__)
    
    
    @classmethod
    def _extract_extras_(
        cls, 
        path : PathLike[str]
    ):
        WarnNotImplemented('_dump_from_from_annotation_', cls.__name__)
    
    @classmethod
    def _request_to_ocr_(
        cls, 
        path              : PathLike[str],
        inetrmediate_path : Optional[PathLike[str]] = None,
    ):
        file_id      = f'tmp-{uuid.uuid4().hex}'
        filename     = os.path.basename(path)
        file_size    = os.path.getsize(path)
        
        # -------- Upload chunks --------
        upload_slices_to_ocr(
            file_id    = file_id,
            path       = path,
            filename   = filename,
            size_bytes = file_size
        )
        
        # -------- Complete upload --------
        remote_file_path = complete_upload_to_ocr(
            file_id    = file_id,
            path       = path,
        )
        
        results, name = predict_in_structure(remote_file_path)
        passages      = group_image_detection_to_passages_json(results)
        return passages
    
    @classmethod
    def _request_captions_from_image_(cls, path : PathLike[str]):
        WarnNotImplemented('_request_captions_from_image_', cls.__name__)
    
    @classmethod
    def _request_segmentation_from_image_(cls, path : PathLike[str]):
        WarnNotImplemented('_request_segmentation_from_image_', cls.__name__)
            
    '''
        All the available method interface registered to IReader.
        Note: Not all subclasses inherited from IReader should implement all methods below 
    '''
    
    _extract_methods_ = {
        'text'    : '_text_based_extraction_',
        'ocr'     : '_ocr_based_extraction_',
        'dump'    : '_dump_from_from_annotation_',
        'caption' : '_request_captions_from_image_',
        'segment' : '_request_segmentation_from_image_'  
    }
    
    @classmethod
    def __call__(
        cls, 
        path       : PathLike[str],
        meth_names : Optional[List[str] | str | None],
        cache_path : PathLike[str],
        **kwargs
    ):
        cls.read(path, meth_names, cache_path, **kwargs)
    
    @abstractmethod
    @classproperty
    def methods(cls):
        return None


@FDManager.register('pdf')
class PDFReader(IReader):
    @classmethod
    def read(
        cls,
        path              : PathLike[str],
        meth_names        : Optional[List[str] | str],
        intermediate_path : Optional[PathLike[str]] = None,
        descriptor        : Optional[FileDesc]    = None,
        **kwargs
    ) -> PDFObject:
        """
        Reads data from a .pdf file using specified extraction methods.

        Args:
            path (PathLike[str]): Path to the file to be read.
            
            meth_name (Optional[List[str] | str | None]): 
                Method(s) to use for extraction. Can be a single method name, a list of method names, or None.
            
            **kwargs: Optional keyword arguments to control extraction behavior.
                text_pages (int or list of int, optional):          Page number(s) to extract using the 'text' method.
                ocr_pages (int or list of int, optional):           Page number(s) to extract using the 'ocr' method.
                cover_pages (int or list of int, optional):         Page number(s) representing the covers
                category_pages (int or list of int, optional):      Page number(s) representing the category
                native_words_intermediate_path (str, optional):     Path to save intermediate results for native words.
                normalized_words_intermediate_path (str, optional): Path to save intermediate results for normalized words.
                sentences_intermediate_path (str, optional):        Path to save intermediate results for sentences.
                paragraphs_intermediate_path (str, optional):       Path to save intermediate results for paragraphs.

            ADDITIONAL NOTE: 
                Either specify text_pages or ocr_pages, not both. If both specified, it will 
                resolve to minimize the usage of OCR, because OCR detection takes more cost.
            
        Returns:
            List: A list of data blocks extracted by the specified methods.

        Raises:
            KeyError: If a specified method in `meth_name` does not exist in `_extract_methods_`.
            TypeError: If `meth_name` is not a string, list, or None.
        """
        
        text_pages     = kwargs.get('text_pages',     [])
        ocr_pages      = kwargs.get('ocr_pages',      [])
        cover_pages    = kwargs.get('cover_pages',    [])
        category_pages = kwargs.get('category_pages', [])
        
        if descriptor is None:
            descriptor = cls.set_descriptor(path, intermediate_path)
        
        meth_names = cls._normalize_methods_(meth_names)
        
        total_pages  = count_pages(path)
        pages_method = cls._record_pages_method_(total_pages, text_pages, ocr_pages, meth_names)
        kwargs['total_pages'] = total_pages
        
        body = PDFBody()
        
        for name in meth_names:
            method = getattr(cls, cls._extract_methods_[name])
            extracted_body = method(
                path,
                intermediate_path = intermediate_path,
                **kwargs
            )
            body.update(extracted_body)
                
        object = PDFObject(
            descriptor     = descriptor,
            total_pages    = total_pages,
            cover_pages    = cover_pages,
            category_pages = category_pages,
            pages_method   = pages_method,
            body           = body
        )
        
        return object

    @classmethod
    def dump(
        cls,
        body : PDFBody,
        path : PathLike[str] = None
    ):
        if path is not None:
            path = Path(path)
            path.mkdir(exist_ok=True)
            
        md_out_path = path / 'paragraphs.md'
        image_dir   = path / 'images'
        vector_dir  = path / 'vectors'
        
        dump_pdf_body_to_md(
            body        = body,
            md_out_path = md_out_path,
            image_dir   = image_dir,
            vector_dir  = vector_dir
        )
    
    @classmethod
    def export(
        cls,
        body : PDFBody,
        desc : FileDesc,
        path : PathLike[str]    
    ):
        if path is not None:
            path = Path(path)
            path.mkdir(exist_ok=True)

        export_path = path / 'chunks.json'
        chunks = group_paragraphs_to_chunks(body.paragraphs)
        
        chunk_list = [
            {
                'content'  : chunk.content,
                'count'    : chunk.count,
                'page_idx' : chunk.page_idx
            }
            for chunk in chunks
        ]
        
        obj = {
            'file_id'   : desc.file_id,
            'file_name' : desc.stem,
            'file_type' : desc.ext,
            'chunks'    : chunk_list
        }
        
        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            
        return len(chunks), obj
    
    
    @classmethod
    def _record_pages_method_(
            cls,
            total_pages : int, 
            text_pages  : List[int], 
            ocr_pages   : List[int], 
            meth_names  : List[str]
        ) -> List[str]:
        
            if len(meth_names) < 1:
                raise ValueError("Methods not specified")
            
            if len(meth_names) == 1:
                meth_name = meth_names[0]
                return [meth_name for i in list(range(1, total_pages+1))]
            else:
                pages_methods = []
                for i in range(total_pages):
                    if i+1 in text_pages:
                        pages_methods.append('text')
                    elif i+1 in ocr_pages:
                        pages_methods.append('ocr')
                    else:
                        pages_methods.append('')                   
                        
    @classmethod
    def _text_based_extraction_(
        cls,
        path              : PathLike[str],
        intermediate_path : PathLike[str],
        **kwargs
    ):
        text_pages     = kwargs.get('text_pages', [])
        ocr_pages      = kwargs.get('ocr_pages', [])
        cover_pages    = kwargs.get('cover_pages', [])
        category_pages = kwargs.get('category_pages', [])
        total_pages    = kwargs['total_pages']
        
        def _get_skipped_pages_(total_pages, text_pages, category_pages, cover_pages, ocr_pages):
            should_skipped_pages = list(set(list(ocr_pages) + list(cover_pages) + list(category_pages)))
            if len(text_pages) < 1: # the case of that 'text_pages' is not specified
                skipped_pages = should_skipped_pages
            else:
                not_skipped_pages    = [p for p in text_pages  if p not in should_skipped_pages]
                skipped_pages        = [p for p in list(range(1, total_pages+1)) if p not in not_skipped_pages]
            return skipped_pages

        skipped_pages = _get_skipped_pages_(
            total_pages, 
            text_pages, 
            category_pages, 
            cover_pages, 
            ocr_pages
        )
            
        body = extarct_pdf_body(
            pdf_path          = path, 
            intermediate_path = intermediate_path, 
            skipped_pages     = skipped_pages
        )
        
        return body
        
    @classmethod
    def _ocr_based_extraction_(
        cls,
        path              : PathLike[str],
        intermediate_path : PathLike[str],
        **kwargs
    ):
        passages = cls._request_to_ocr_(path)
        paragraphs = [
            Paragraph(
                page_ids = passage['page_number'],
                content  = passage['content'],
                count    = passage['count']
            ) for passage in passages
        ]
        
        total_words = 0
        
        for paragraph in paragraphs:
            total_words += paragraph.count
            
        body = PDFBody(
            paragraphs  = paragraphs,
            figures     = [],
            vgraphics   = [],
            total_words = total_words
        )
        
        return body
        
    @classproperty
    def methods(cls):
        return ['text', 'ocr']


@FDManager.register('docx')
class DOCXReader(IReader):
    @classmethod
    def read(
        cls,
        path              : PathLike[str],
        meth_names        : Optional[List[str] | str | None],
        intermediate_path : PathLike[str] = None,
        descriptor        : Optional[FileDesc]    = None,
        **kwargs
    ):
        if descriptor is None:
            descriptor = cls.set_descriptor(path, intermediate_path)
        meth_names = cls._normalize_methods_(meth_names)
        
        body = DOCXBody()
        for name in meth_names:
            method = getattr(cls, cls._extract_methods_[name])
            extracted_body = method(
                path,
                cache_path = intermediate_path,
                **kwargs
            )
            body.update(extracted_body)
        
        object = DOCXObject(
            descriptor   = descriptor,
            body         = body
        )

        return object
    
    
    @classmethod
    def dump(
        cls,
        body : DOCXBody,
        path : PathLike[str] = None
    ):
        if path is not None:
            path = Path(path)
            path.mkdir(exist_ok=True)
            
        md_out_path = path / 'paragraphs.md'
        image_dir   = path / 'images'
        
        dump_docx_body_to_md(
            body        = body,
            md_out_path = md_out_path,
            image_dir   = image_dir
        )
        
        
    @classmethod
    def export(
        cls,
        body : DOCXBody,
        desc : FileDesc,
        path : PathLike[str]    
    ):
        if path is not None:
            path = Path(path)
            path.mkdir(exist_ok=True)

        export_path = path / 'chunks.json'
        chunks = group_paragraphs_to_chunks(body.paragraphs)
        
        chunk_list = [
            {
                'content'  : chunk.content,
                'count'    : chunk.count,
                'page_idx' : chunk.page_idx
            }
            for chunk in chunks
        ]
        
        obj = {
            'file_id'   : desc.file_id,
            'file_name' : desc.stem,
            'file_type' : desc.ext,
            'chunks'    : chunk_list
        }

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
            
        return len(chunks), obj
    
    
    @classmethod
    def _text_based_extraction_(
        cls, 
        path              : PathLike[str],
        intermediate_path : PathLike[str] = None,
        **kwargs
    ) -> DOCXBody:
        return extract_docx_body(path, intermediate_path)
        # return super()._text_based_extractor_(path, cache_path, **kwargs)
    
    
    @classproperty
    def methods(cls):
        return ['text']
    

@FDManager.register('png', 'jpg', 'jpeg')
class ImageReader(IReader):
    @classmethod
    def read(
        cls,
        path              : PathLike[str],
        meth_names        : Optional[List[str] | str | None],
        intermediate_path : PathLike[str],
        descriptor        : Optional[FileDesc]    = None,
        **kwargs
    ) -> ImageObject:
        if descriptor is None:
            descriptor = cls.set_descriptor(path, intermediate_path)
        meth_names = cls._normalize_methods_(meth_names)
        
        if len(meth_names) > 1:
            raise ValueError(f"Only one method is allowed, try to pick one across {meth_names}")
        
        body = ImageBody()
        for name in meth_names:
            method = getattr(cls, cls._extract_methods_[name])
            extracted_body = method(
                path,
                cache_path=intermediate_path,
                **kwargs
            )
            body.update(extracted_body)
        
        object = ImageObject(
            descriptor = descriptor,
            body       = body
        )
        
        return object
        
    @classmethod
    def dump(
        cls,
        body : ImageBody,
        path : PathLike[str] = None
    ):
        if path is not None:
            path = Path(path)
            path.mkdir(exist_ok=True)
            
        md_out_path = path / 'paragraphs.md'
        image_dir   = path / 'images'
        
        dump_image_body_to_md(
            body        = body,
            md_out_path = md_out_path,
            image_dir   = image_dir
        )
        
        
    @classmethod
    def export(
        cls,
        body : ImageBody,
        desc : FileDesc,
        path : PathLike[str]    
    ):
        if path is not None:
            path = Path(path)
            path.mkdir(exist_ok=True)

        export_path = path / 'chunks.json'
        chunks = group_paragraphs_to_chunks(body.paragraphs)
        
        chunk_list = [
            {
                'content'  : chunk.content,
                'count'    : chunk.count,
                'page_idx' : chunk.page_idx
            }
            for chunk in chunks
        ]
        
        obj = {
            'file_id'   : desc.file_id,
            'file_name' : desc.stem,
            'file_type' : desc.ext,
            'chunks'    : chunk_list
        }

        with open(export_path, 'w', encoding='utf-8') as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        
        return len(chunks), obj
    
    
    @classmethod
    def _ocr_based_extraction_(
        cls,
        path              : PathLike[str],
        # intermediate_path : PathLike[str],
        **kwargs
    ):
        passages = cls._request_to_ocr_(path)
        paragraphs = [
            Paragraph(
                page_ids = passage['page_number'],
                content  = passage['content'],
                count    = passage['count']
            ) for passage in passages
        ]
        
        total_words = 0
        
        for paragraph in paragraphs:
            total_words += paragraph.count
            
        body = ImageBody(
            paragraphs  = paragraphs,
            figures     = [],
            total_words = total_words
        )
        
        return body
    
    @classproperty
    def methods(cls):
        return ['ocr', 'caption']
    

@FDManager.register('md')    
class MarkdownReader(IReader):    
    @classmethod
    def read(cls):
        pass

    @classproperty
    def methods(cls):
        return ['text', 'ocr']
    

@FDManager.register('/dir')
class DirectoryReader(IReader):
    @classmethod
    def read(cls):
        pass
    
    @classproperty
    def methods(cls):
        return list(cls._extract_methods_.keys())
