from .rr.upload import (
    ReqCompleteUpload,
    RespUploading,
    RespFileStatus
)

from .rr.generic   import RespStatus
from ..mdo.engine.manager.driver import FileManager
from ..mdo.io.file.generic       import FileStage, FileRecord
from mondoo.configurator   import get_global_config_value

from pathlib               import Path
from datetime              import datetime, timezone
from fastapi               import FastAPI, Form, HTTPException, Request
from fastapi               import UploadFile
from fastapi.responses     import HTMLResponse
from fastapi.openapi.utils import get_openapi

import mondoo.mdo.api.fsys as ifsys
import os
import asyncio
import logging


logger = logging.getLogger(__name__)


SERVER_URL = set(os.getenv('PROXY_URL', '127.0.0.1').split(','))
logger.info(f"Proxy URLs: {SERVER_URL}")


ALLOWED_IPS = set(os.getenv('ALLOWED_INCOMING_IPS', '127.0.0.1').split(','))
logger.info(f"Allowed Incoming IPs: {ALLOWED_IPS}")


app = FastAPI(
    title       = "Files Service",
    docs_url    = "/docs",
    openapi_url = "/openapi.json",
    servers     = [
        {
            'url': SERVER_URL,
            'description': "Nginx reverse proxy"
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
        record.stage            = FileStage.CACHED
        record.total_chunks     = num_chunks
        FileManager.record(file_id, record)


@app.get("/api/v1/files/upload")
async def index():
    return HTMLResponse("""
<html>
<body>
<h3>Chunked File Upload with WebSocket Progress</h3>
<label>
  <input type="checkbox" id="ifImage" checked />
  If it's in image modality?
</label>

<input type="file" id="fileInput"/>
<button onclick="upload()">Upload</button>
<button onclick="showFileList()">Show Uploaded Files</button>

<button onclick="deleteAllFiles()" style="margin-top:10px; color:white; background-color:red;">
  Clean All File Records
</button>

<div id="progress">0%</div>
<div id="fileList"></div>

<script>

function nowMs() {
    const d = new Date();
    return d.toISOString().replace("T", ".").replace("Z", "").replace(/[:-]/g, ".");
}

function uuidv4() {
  if (crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return ([1e7]+-1e3+-4e3+-8e3+-1e11).replace(/[018]/g, c =>
    (c ^ crypto.getRandomValues(new Uint8Array(1))[0] & 15 >> c / 4).toString(16)
  );
}

async function upload() {
    const uploadStartTime = Date.now(); // ms since epoch
    console.log("Upload started at:", new Date(uploadStartTime).toISOString());
    
    const file = document.getElementById('fileInput').files[0];
    if (!file) return alert("Choose a file first!");

    const fileId      = uuidv4();
    const sliceSize   = 1024 * 1024; // 1MB
    const totalSlices = Math.ceil(file.size / sliceSize);

    // Step 1: Upload slices
    for (let i = 0; i < totalSlices; i++) {
        const chunk = file.slice(i * sliceSize, (i + 1) * sliceSize);

        const formData = new FormData();
        formData.append('file', chunk);
        formData.append("filename", file.name);
        formData.append("slice_index", i);
        formData.append("total_slices", totalSlices);
        
        const startTs = Date.now();
        
        try {
            const resp = await fetch(
                `/ragai/kbase/files/${fileId}/slices/${i}`,
                {
                    method: "PUT",
                    body: formData,
                    headers: {
                        "x-upload-timestamp": startTs.toString()
                    }
                }
            );
            const endTs = Date.now(); // ⬅ end timestamp
            const durationMs = endTs - startTs;
            
            if (!resp.ok) throw new Error(`Chunk ${i} failed`);
            const data = await resp.json();
            
            document.getElementById('progress').innerText =
                `Slices ${i + 1}/${totalSlices} | \n` +
                `Client Send Time: ${data.client_send_time} | \n` +
                `Server Recv Time: ${data.server_recv_time} | \n` +
                `Transfer Duration: ${data.transfer_duration} | \n` +
                `Server Save Duration: ${data.server_save_duration} | \n` +
                `Total: ${data.percent}%`;
            
        } catch (err) {
            alert(`Upload failed at chunk ${i}: ${err}`);
            return;
        }
    }

    // Step 2: Poll final status
    let statusResp = await fetch(`/ragai/kbase/files/${fileId}/status`);
    let statusData = await statusResp.json();
    document.getElementById('progress').innerText = `Uploaded ${statusData.percent}%`;

    checked = document.getElementById('ifImage').checked
    let parse_meth = 'text'
    if (checked) {
        parse_meth = 'ocr'
    }
    
    // Step 3: Complete upload
    const completeResp = await fetch(`/ragai/kbase/files/${fileId}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            parse_meth,
            should_cache:   true,
            should_offline: true,
            should_store:   true
        })
    });

    if (!completeResp.ok) {
        alert("Failed to complete upload");
        return;
    }

    const completeData = await completeResp.json();
    document.getElementById('progress').innerText = `Upload complete! File ID: ${completeData.file_id}`;
}

function fixedLength(str, length = 20) {
    if (str.length > length) return str.slice(0, length - 3) + '...'; // truncate
    return str.padEnd(length, ' '); // pad with spaces
}

async function showFileList() {
    const fileListDiv = document.getElementById('fileList');
    fileListDiv.innerHTML = "Loading...";

    try {
        const resp = await fetch('/ragai/kbase/files/');
        if (!resp.ok) throw new Error("Failed to fetch file list");

        const data = await resp.json();
        const files = data.views;

        if (files.length === 0) {
            fileListDiv.innerHTML = "<i>No completed files</i>";
            return;
        }

        const ul = document.createElement("ul");
        for (const f of files) {
            const li = document.createElement("li");

            const info = document.createElement("span");
            info.textContent =
                `${f.filename} | type: ${f.type} | stage: ${f.stage} | size: ${f.size} bytes | chunks: ${f.num_chunk}`;

            const btn = document.createElement("button");
            btn.textContent = "Delete";
            btn.style.marginLeft = "10px";
            btn.onclick = () => deleteFile(f.file_id);

            li.appendChild(info);
            li.appendChild(btn);

            ul.appendChild(li);
        }
        fileListDiv.innerHTML = ""; // clear loading
        fileListDiv.appendChild(ul);

    } catch (err) {
        fileListDiv.innerHTML = `Error: ${err}`;
    }
}

async function deleteFile(fileId) {
    if (!confirm("Delete this file?")) return;

    try {
        const resp = await fetch(`/ragai/kbase/files/${fileId}`, {
            method: "DELETE"
        });

        if (!resp.ok) {
            throw new Error("Failed to delete file");
        }

        const data = await resp.json();

        alert(`File ${data.file_id} deleted`);
        showFileList(); // refresh list

    } catch (err) {
        alert(`Delete error: ${err}`);
    }
}

async function deleteAllFiles() {
    if (!confirm("Are you sure you want to delete ALL files?")) return;

    try {
        const resp = await fetch('/ragai/kbase/files/', {
            method: 'DELETE'
        });

        if (!resp.ok) {
            throw new Error("Failed to delete all files");
        }

        const data = await resp.json();
        alert("All files deleted successfully!");

        // Refresh the file list
        showFileList();

    } catch (err) {
        alert(`Error deleting all files: ${err}`);
    }
}

</script>

</body>
</html>
""")


'''
@app.middleware('http')
async def token_auth_middleware(request: Request, call_next):
    auth_header = request.headers.get('Authorization', None)

    if not auth_header:
        raise HTTPException(
            status_code = 401,
            detail      = "Missing Authorization header"
        )

    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise ValueError
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization format"
        )

    if token not in VALID_TOKENS:
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication token"
        )

    return await call_next(request)
'''


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
    upload_dir = FileManager.source_dir
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
    
    record    = FileManager.get(file_id)
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
    
    await FileManager.record_async(file_id, record)
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
    upload_dir = FileManager.source_dir
    object_dir = FileManager.object_dir
    record     = FileManager.get(file_id)
    
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
    
    if record.stage in [FileStage.UPLOADED, FileStage.CACHED, FileStage.STORED]:
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
    await FileManager.record_async(file_id, record) 

    if req.should_cache:
        if req.should_offline:
            func = launch_parse_file_task_thread
            asyncio.create_task(
                asyncio.to_thread(func, file_id, source_path, record, req.parse_meth)
            )
        else:
            await ifsys.do_parse_file_task_async(
                file_id, 
                source_path, 
                record, 
                req.parse_meth
            )

    return RespFileStatus(
        status  = RespStatus.OK,
        file_id = file_id,
        stage   = record.stage
    )


@app.get('/api/v1/files/{file_id}/status', response_model=RespFileStatus)
def get_file_status(file_id: str):
    record = FileManager.get(file_id)
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
    record = FileManager.get(file_id)
    if not record:
        hint = f"Record not found: <{file_id}>"
        logger.warning(hint) 
        raise HTTPException(status_code=500, detail=hint) 

    file_path  = record.desc.source_path
    cache_path = record.desc.target_path

    try: # remove from database
        FileManager.remove(file_id)
    except Exception as e:
        hint = f"\"Failed to remove record from database\": {str(e)}"
        logger.warning(hint)
        raise HTTPException(status_code=500, detail=hint)

    try: # remove source and cached files
        ifsys.remove_file(file_path)
        ifsys.remove_cache(cache_path)
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

      
@app.post('/api/v1/files/{file_id}/cache?={parse_meth}')
def cache_file(file_id : str, parse_meth : str):
    upload_dir = FileManager.source_dir  
    record = FileManager.get(file_id)
    
    if not record: raise HTTPException(404, "Record not found")
    if record.stage != FileStage.UPLOADED:
        raise HTTPException(400, "File not yet completed")
    
    path = os.path.join(upload_dir, record['filename'])
    ifsys.launch_cache_file_task_thread(file_id, path, record, parse_meth)
    record.stage = FileStage.CACHED
    
    return RespFileStatus(
        status  = RespStatus.OK,
        file_id = file_id,
        stage   = FileStage.CACHED
    )
    
    
@app.get('/api/v1/files')
def get_file_views():
    records : list[FileRecord] = FileManager.get_all()
    views  = []
    for record in records:
        views.append(record.view)
    
    return { 
        'status' : 'ok',
        'views'  : views
    }


@app.get('/api/v1/files/context')
def get_file_context():
    context = FileManager.context
    return { 
        'status'  : 'ok',
        'context' : context
    }


@app.get('/api/v1/files/{ext}/methods')
def get_available_methods(ext : str):
    return {
        'status' : 'ok',
        'methods': FileManager.get_available_methods(ext)
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