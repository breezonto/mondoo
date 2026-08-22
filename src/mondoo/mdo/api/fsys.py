from ..engine.manager.file_descriptor       import FDManager
from ..io.file.generic     import FileDesc, FileStage, FileRecord

import requests
import logging
import threading
import json
import os
import shutil


logger = logging.getLogger(__name__)


file_task_lock = threading.Lock()


def remove_src_file(path):
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    
    if os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    else:
        raise FileNotFoundError(path)


def remove_fd_file(path):
    if not path or not os.path.exists(path):
        raise FileNotFoundError(f"Cache not found: {path}")
    
    if os.path.isfile(path):
        os.remove(path)
    elif os.path.isdir(path):
        shutil.rmtree(path)
    else:
        raise FileNotFoundError(f"Invalid cache path: {path}")
    

def parse(
    file_id   : str,
    file_path : str,
    method    : str
):  
    logger.info("\"Start to Cache File with Method [%s]: [%s]\"", method, file_id)
    try:
        objs = FDManager.parse(
            path        = file_path,
            meth_names  = [method],
            file_id     = file_id
        )
        
        for obj in objs:
            result_path = FDManager.dump(obj)
            cache_path, num_chunks, ret_obj = FDManager.export(obj)
            
            # send_request_to_pg('write_json',
            #     file_id   = file_id,
            #     json_col  = 'chunks',
            #     json_data = ret_obj
            # )
            # send_md_to_backend(os.path.join(result_path, 'paragraphs.md'))
    
    except Exception as e:
        logger.error("\"Error occur when caching file [%s]: %s\"", str(file_id), str(e))
    
    logger.info("\"Complete to Cache File with Method [%s]: [%s]\"", method, file_id)

    return cache_path, num_chunks


async def do_parse_file_task_async(
    file_id    : str,
    path       : str,
    record     : FileRecord,
    parse_meth : str
):
    target_path, num_chunks = parse(
        file_id, 
        file_path = path,
        method    = parse_meth
    )
    
    with file_task_lock:
        record.desc.target_path = target_path
        record.stage            = FileStage.CACHED
        record.total_chunks     = num_chunks
        await FDManager.archive(file_id, record)

    return target_path