from mondoo.mdo.engine.manager.file_descriptor import FDManager
from mondoo.mdo.io.parser.generic              import FileStage, FileRecord

from .rr.generic import RespStatus
from .rr.upload  import (
    ReqCompleteUpload,
    RespUploading,
    RespFileStatus,
    ReqExtract
)

from pathlib               import Path
from datetime              import datetime, timezone
from fastapi               import FastAPI, Form, HTTPException, Request
from fastapi               import UploadFile
from fastapi.openapi.utils import get_openapi

import mondoo.mdo.api.fsys as ifsys
import os
import logging


logger = logging.getLogger(__name__)


SERVER_URL = os.getenv('PROXY_URL', None)
logger.info(f"Proxy URLs: {SERVER_URL}")

ALLOWED_IPS = os.getenv('ALLOWED_INCOMING_IPS', '127.0.0.1')
logger.info(f"Allowed Incoming IPs: {ALLOWED_IPS}")

PSQL_HOST = os.getenv('PSQL_HOST', None)
PSQL_PORT = os.getenv('PSQL_PORT', None)
PSQL_DB   = os.getenv('PSQL_DB', None)
logger.info(f"PostgreSQL Connection: {PSQL_HOST}:{PSQL_PORT}@{PSQL_DB}")


app = FastAPI(
    title       = "Files Service",
    docs_url    = "/docs",
    openapi_url = "/openapi.json",
    servers     = [
        {
            'url'         : SERVER_URL,
            'description' : "Nginx reverse proxy"
        }
    ]
)


def launch_parse_file_task_thread(
    file_id    : str,
    path       : str,
    record     : FileRecord,
    parse_meth : str
):
    cache_path, num_chunks = ifsys.parse(
        file_id, 
        file_path       = path,
        method = parse_meth
    )
    
    with ifsys.file_task_lock:
        record.desc.target_path = cache_path
        record.stage            = FileStage.PARSED
        record.total_chunks     = num_chunks
        FDManager.archive(file_id, record)


@app.middleware('http')
async def ip_filter_middleware(request: Request, call_next):
    # This is the remote IP as seen by FastAPI
    remote_ip = request.client.host
    if remote_ip not in ALLOWED_IPS:
        # Block the request
        raise HTTPException(status_code=403, detail=f"Forbidden: {remote_ip} not allowed")
    
    # Continue processing
    response = await call_next(request)
    return response


@app.put("/api/v1/files/{file_id}/slices/{slice_index}", response_model=RespUploading)
async def upload_slice(
    file_id      : str,
    slice_index  : int,
    request      : Request,
    file         : UploadFile,
    filename     : str = Form(...),
    total_slices : int = Form(...)
):
    upload_dir = FDManager.source_dir
    os.makedirs(os.path.join(upload_dir, file_id), exist_ok=True)
    
    server_recv_dt = datetime.now(timezone.utc)
    def _measure_latency_():
        server_recv_str = server_recv_dt.strftime(
            "%Y-%m-%d %H:%M:%S."
        ) + f"{server_recv_dt.microsecond // 1000:03d}"
        
        upload_timestamp = request.headers.get("x-upload-timestamp", None)
        
        client_send_dt        = None
        client_send_str       = 'N/A'
        transfer_duration_str = 'N/A'
        
        if upload_timestamp:
            try:
                client_send_dt = datetime.fromtimestamp(
                    int(upload_timestamp) / 1000,
                    tz=timezone.utc
                )
                client_send_str = client_send_dt.strftime(
                    "%Y-%m-%d %H:%M:%S."
                ) + f"{client_send_dt.microsecond // 1000:03d}"

                transfer_duration_ms = (server_recv_dt - client_send_dt).total_seconds() * 1000
                transfer_duration_str = f"{transfer_duration_ms:.3f} ms"

            except (ValueError, OverflowError):
                # malformed client timestamp
                pass
        else:
            transfer_duration_ms = None
            transfer_duration_str = 'N/A'

        return client_send_str, server_recv_str, transfer_duration_str
    
    client_send_str, server_recv_str, transfer_duration_str = _measure_latency_()
    
    record    = FDManager.query(file_id)
    slice_dir = os.path.join(upload_dir, file_id)
    basename  = Path(filename).stem
    ext       = Path(filename).suffix.lstrip(".")
    
    if not record:
        record = FileRecord.create(
            id           = file_id,
            source_path  = slice_dir,
            target_path  = '',
            stem         = basename,
            ext          = ext,
            size         = -1,
            stage        = FileStage.UPLOADING,
            curr_slice   = slice_index,
            total_slices = total_slices,
            total_chunks = 0
        )
        
    else:    
        if record.stage == FileStage.UPLOADED: 
            raise HTTPException(400, "File already exists")

        record = FileRecord(
            desc         = record.desc,
            stage        = FileStage.UPLOADING,
            curr_slice   = slice_index,
            total_slices = total_slices,
            total_chunks = 0
        )
    
    # write to file
    slice_path = os.path.join(slice_dir,  f'{slice_index:06d}.part')
    with open(slice_path, 'wb') as f: f.write(await file.read())    
    
    await FDManager.archive_in_async(file_id, record)
    percent                = float(slice_index + 1) / float(total_slices) * 100
    server_save_dt         = datetime.now(timezone.utc)
    save_duration_ms       = (server_save_dt - server_recv_dt).total_seconds() * 1000
    save_duration_time_str = f"{save_duration_ms:.3f} ms"
    
    return RespUploading(
        status               = RespStatus.OK,
        slice_index          = slice_index,
        percent              = percent,
        client_send_time     = client_send_str,
        server_recv_time     = server_recv_str,
        transfer_duration    = transfer_duration_str,
        server_save_duration = save_duration_time_str
    )
    
        
@app.post("/api/v1/files/{file_id}", response_model=RespFileStatus)
async def complete(
    file_id : str, 
    req     : ReqCompleteUpload
):
    upload_dir = FDManager.source_dir
    object_dir = FDManager.object_dir
    record     = FDManager.query(file_id)
    
    def _merge_slices_(file_path):
        with open(file_path, 'wb') as outfile:
            for i in range(record.total_slices):
                part_path = os.path.join(upload_dir, file_id, f'{i:06d}.part')
                with open(part_path, 'rb') as infile:
                    outfile.write(infile.read())
                os.remove(part_path)
            
            size_bytes = outfile.tell()
        os.rmdir(os.path.join(upload_dir, file_id))
        
        return size_bytes
    
    if not record:
        logger.error("Record %s not found: %s", str(file_id), str(record))
        raise HTTPException(404, "Record not found")
    
    if record.stage in [FileStage.UPLOADED, FileStage.PARSED, FileStage.STORED]:
        return RespFileStatus(
            status  = RespStatus.OK,
            file_id = file_id,
            stage   = record.stage
        )
    
    def _valiate_uploading_():
        curr_slice = record.curr_slice
        total      = record.total_slices
        if (curr_slice + 1) != total: raise HTTPException(400, "Not all chunks uploaded")
        
    _valiate_uploading_()

    basename    = record.desc.stem
    ext         = record.desc.ext
    source_path = os.path.join(upload_dir, '.'.join([basename, ext]))
    size_bytes  = _merge_slices_(source_path)
    
    record.desc.file_id     = file_id
    record.desc.size        = size_bytes
    record.desc.source_path = source_path
    if record.total_slices < 2:
        record.curr_slice += 1

    record.stage = FileStage.UPLOADED
    await FDManager.archive_in_async(file_id, record) 
    return RespFileStatus(
        status  = RespStatus.OK,
        file_id = file_id,
        stage   = record.stage
    )

    # if req.should_cache:
    #     if req.should_offline:
    #         func = launch_parse_file_task_thread
    #         asyncio.create_task(
    #             asyncio.to_thread(func, file_id, source_path, record, req.parse_meth)
    #         )
    #     else:
    #         await ifsys.do_parse_file_task_async(
    #             file_id, 
    #             source_path, 
    #             record, 
    #             req.parse_meth
    #         )


@app.post('/api/v1/files/{file_id}/extraction')
async def extract(
    file_id : str,
    req     : ReqExtract
):
    record = FDManager.query(file_id)
    await ifsys.do_parse_file_task_async(
        file_id, 
        record.desc.source_path, 
        record, 
        req.method_name
    )




@app.get('/api/v1/files/{file_id}/status', response_model=RespFileStatus)
async def get_file_status(file_id: str):
    record = FDManager.query(file_id)
    if not record:
        logger.warning("Record not found: %s", file_id)
        raise HTTPException(status_code=404, detail="Record not found")
    
    return RespFileStatus(
        status  = RespStatus.OK,
        file_id = file_id,
        stage   = record.stage
    )


@app.delete('/api/v1/files/{file_id}', response_model=RespFileStatus)
async def remove_file(file_id: str):
    record = FDManager.query(file_id)
    if not record:
        hint = f"Record not found: <{file_id}>"
        logger.warning(hint) 
        raise HTTPException(status_code=500, detail=hint) 

    file_path  = record.desc.source_path
    cache_path = record.desc.target_path

    try: # remove from database
        FDManager.erase(file_id)
    except Exception as e:
        hint = f"\"Failed to remove record from database\": {str(e)}"
        logger.warning(hint)
        raise HTTPException(status_code=500, detail=hint)

    try: # remove source and cached files
        ifsys.remove_src_file(file_path)
        ifsys.remove_fd_file(cache_path)
    except FileNotFoundError as e:
        hint = f"\"Delete resource missing for <{file_id}>: {str(e)}\""
        logger.warning(hint)
        raise HTTPException(status_code=404, detail=hint)
    except Exception:
        hint = f"\"Unexpected error while removing <{file_id}>\""
        logger.exception(hint)
        raise HTTPException(status_code=404, detail=hint)
    
    return RespFileStatus(
        status  = RespStatus.OK,
        file_id = file_id, 
        stage   = FileStage.DELETED
    )
    
    
@app.get('/api/v1/files')
def get_file_views():
    records : list[FileRecord] = FDManager.query_all()
    views  = []
    for record in records:
        views.append(record.view)
    
    return { 
        'status' : 'ok',
        'views'  : views
    }


@app.get('/api/v1/files/context')
def get_file_context():
    context = FDManager.context
    return { 
        'status'  : 'ok',
        'context' : context
    }


@app.get('/api/v1/files/{ext}/methods')
def get_available_methods(ext : str):
    return {
        'status' : 'ok',
        'methods': FDManager.get_available_methods(ext)
    }

    
def custom_openapi():
    # if app.openapi_schema:
    #     return app.openapi_schema

    schema = get_openapi(
        title   = app.title,
        version = "1.0",
        routes  =app.routes,
    )

    new_paths = {}

    for path, value in schema["paths"].items():
        new_path = path.replace("/api/v1/", "/ragai/kbase/")
        new_paths[new_path] = value
        print(f'{path} to {new_path}')
    
    schema["paths"] = new_paths

    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi