from mondoo.mdo.engine.configurator import BACKEND_BASE, MCP_LOGGING_YAML_PATH

from datetime import datetime
from os       import PathLike
from typing   import List, Optional, Dict
from pathlib  import Path
from pydantic import BaseModel, ConfigDict

import time
import math
import requests
import fitz
import pdfplumber
import yaml


class Page:
    def __init__(
        self,
        method,
        page_idx,
        page_width, 
        page_height,
        **kwargs
    ):
        self.page_type   = method
        self.page_idx    = page_idx
        self.page_width  = page_width
        self.page_height = page_height
        

class Paragraph:
    def __init__(
        self,
        page_ids : List[int], 
        content  : str, 
        count    : int = 0
    ):
        self.page_ids = page_ids
        self.content  = content
        self.count    = count if count != 0 else len(content)
        
    def to_dict(self) -> Dict:
        return dict(self.__dict__)


class Chunk:
    def __init__(
        self,
        content : str,
        page_idx : List[int],
        count : int = 0
    ):
        self.content = content
        self.page_idx = page_idx
        self.count = count if count > 0 else len(content)
        
    def to_dict(self) -> Dict:
        return dict(self.__dict__)


class Figure:
    def __init__(
        self,
        page_ids    : List[int],
        image_bytes : bytes,
        image_ext   : str,
        index       : int,
        width       : Optional[int] = None,
        height      : Optional[int] = None,
    ):
        self.image_bytes = image_bytes   # raw image bytes
        self.image_ext   = image_ext     # "png", "jpg", etc.
        self.page_ids    = page_ids
        self.index       = index
        self.width       = width
        self.height      = height

    def to_dict(self) -> Dict:
        return {
            'page_ids'  : self.page_ids,
            'index'     : self.index,
            'image_ext' : self.image_ext,
            'width'     : self.width,
            'height'    : self.height,
            # NOTE: image_bytes intentionally omitted
        }
    
    def export(self, output_dir: Path) -> Path:
        """
        Save the illustration image to disk and return the file path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = (
            f"page_{'_'.join(map(str, self.page_ids))}"
            f"_img_{self.index}.{self.image_ext}"
        )
        out_path = output_dir / filename

        with open(out_path, "wb") as f:
            f.write(self.image_bytes)

        return out_path
                
        
class VectorGraphic:
    def __init__(
        self,
        page_ids: List[int],
        pixmap: fitz.Pixmap,
        index: int,
    ):
        self.pixmap   = pixmap          # fitz.Pixmap object
        self.page_ids = page_ids
        self.index    = index
        self.width    = pixmap.width
        self.height   = pixmap.height

    def to_dict(self) -> Dict:
        return {
            "page_ids": self.page_ids,
            "index": self.index,
            "width": self.width,
            "height": self.height,
            # pixmap omitted (not JSON-serializable)
        }

    def export(self, output_dir: Path, ext: str = "png") -> Path:
        """
        Save the vector graphic to disk and return the file path.
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = (
            f"page_{'_'.join(map(str, self.page_ids))}"
            f"_vector_{self.index}.{ext}"
        )
        out_path = output_dir / filename

        self.pixmap.save(out_path)

        return out_path


class BaseModelWithBody(BaseModel):
    model_config = ConfigDict(
        arbitrary_types_allowed=True
    )

    def model_dump(self, **kwargs):
        # dump Pydantic fields normally
        d = super().model_dump(**kwargs)
        # convert body manually
        if self.body is not None:
            d['body'] = self.body.to_dict()
        return d


SLICE_SIZE = 1 * 1024 * 1024


def upload_slices_to_ocr(
    file_id    : str,
    path       : PathLike[str],
    filename   : str,
    size_bytes : int  
):
    total_slices = math.ceil(size_bytes / SLICE_SIZE)
    # -------- Upload slices to ocr --------
    with open(path, "rb") as f:
        for slice_index in range(total_slices):
            chunk_data = f.read(SLICE_SIZE)
            if not chunk_data:
                break

            url = (f'{BACKEND_BASE}:7960/api/v1/files/{file_id}/slices/{slice_index}')

            headers = { 'x-upload-timestamp': str(int(time.time() * 1000)) }
            files   = { 'file': (filename, chunk_data, 'application/octet-stream') }
            data    = { 'filename': filename, 'total_slices': str(total_slices) }
            print(f"Slice {slice_index}: send request")
            
            try:
                resp = requests.put(
                    url,
                    headers = headers,
                    files   = files,
                    data    = data,
                    timeout = 500
                )

                resp.raise_for_status()
                data = resp.json()
            
            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"Internal HTTP Error in Putting Slice {slice_index}: {str(e)} ") from e
            except Exception as e:
                raise RuntimeError(f"Other Runtime Error in Putting Slice {slice_index}: {str(e)}") from e


def complete_upload_to_ocr(
    file_id,
    path,
    parse_meth = 'text'
):
    url = f'{BACKEND_BASE}:7960/api/v1/files/{file_id}'

    payload = {
        'parse_meth'     : parse_meth, # it doesn't take any effect
        'should_cache'   : False,
        'should_store'   : False,
        'should_offline' : False
    }
    
    resp = requests.post(
        url     = url,
        json    = payload,
        timeout = 500
    )
    
    resp.raise_for_status()
    print(f"[UPLOAD] completing file_id={file_id}")
    data = resp.json()
    
    status = data.get('status', '')
    
    if status == 'ok':
        pass
    
    remote_file_path = data.get('file_path')
    
    resp.raise_for_status()
    
    print("[PREDICT] returned successfully")
    
    return remote_file_path


def predict_in_structure(file_path):
    url = f'{BACKEND_BASE}:7960/api/v1/ocr/predict'
    payload = {
        'file_path'      : file_path,
        'should_offline' : False
    }
    try:
        print(f"Sending Request [POST] {url} in background")
        resp = requests.post(url, json=payload, timeout=500)
        
        resp.raise_for_status()
        
        data = resp.json()
        if data.get('status') == "ok":
            results = data.get('results')
            name = data.get('name')
            return results, name
            print("Case 0 [predict_in_structure]: Background for cache and store SUCCESSED")
        else:
            print("Case 1 [predict_in_structure]: Background for cache and store FAILED")
    
    except Exception as e:
        error = str(e)
        print(f"Case 2 [predict_in_structure]: Background for cache and store FAILED:\n{error}")


def group_image_detection_to_passages(results):
    passages = []
    for page_idx, result in enumerate(results, start=1):
        res_obj = result.json['res']
        parsing_res_list = res_obj.get('parsing_res_list', [])
        
        content = ''
        for res_block in parsing_res_list:
            label = res_block['block_label']
            if label == 'paragraph_title':
                content += ''.join([res_block['block_content'], '\n'])
            elif label == 'text':
                content += res_block['block_content']
        
        passages.append(
            {
                'page_number': [page_idx],
                'content': content
            }
        )
    
    return passages


def group_image_detection_to_passages_json(results):
    passages = []
    for page_idx, result in enumerate(results, start=1):
        res_obj = result['res']
        parsing_res_list = res_obj.get('parsing_res_list', [])
        
        content = ''
        for res_block in parsing_res_list:
            label = res_block['block_label']
            if label == 'paragraph_title':
                content += ''.join([res_block['block_content'], '\n'])
            elif label == 'text':
                content += res_block['block_content']
        
        passages.append(
            {
                'page_number' : [page_idx],
                'content'     : content,
                'count'       : len(content)
            }
        )
    
    return passages


def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


BASE_LOG_DIR = Path('logs')


def setup_mcp_logging(mcp_server_name: str):
    config_path = MCP_LOGGING_YAML_PATH

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Create service log directory
    service_log_dir = BASE_LOG_DIR / 'mcp' / mcp_server_name
    service_log_dir.mkdir(parents=True, exist_ok=True)

    # Create timestamped logfile
    ts = get_timestamp()

    logfile = service_log_dir / f"{mcp_server_name}-{ts}.log"

    # Inject logfile path
    config["handlers"]["mcp_file"]["filename"] = str(logfile)

    # logging.config.dictConfig(config)

    return config