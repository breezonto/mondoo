from mondoo.configurator import get_global_config_value, SERVER_URL, ALLOWED_IPS
from ..mdo.engine.dbc    import get_current_async_dbc
from .rr.vkbase       import *   
from .rr.generic      import RespStatus

from fastapi import FastAPI, Form, HTTPException, Request, File, UploadFile
from fastapi import Query

import mondoo.mdo.api.knowledge as IK

import logging
import os

logger = logging.getLogger(__name__)


SERVER_URL = set(os.getenv('PROXY_URL', '127.0.0.1').split(','))
logger.info(f"Proxy URLs: {SERVER_URL}")


ALLOWED_IPS = set(os.getenv('ALLOWED_INCOMING_IPS', '127.0.0.1').split(','))
logger.info(f"Allowed Incoming IPs: {ALLOWED_IPS}")


app = FastAPI(
    title       = "Knowledge Base Service",
    servers     = [
        { 
            'url': SERVER_URL, 
            'description': "Nginx reverse proxy path" 
        }
    ],
    docs_url    = '/docs',
    redoc_url   = '/redoc',
    openapi_url = '/openapi.json'
)


@app.middleware('http')
async def ip_filter_middleware(request: Request, call_next):
    # This is the remote IP as seen by FastAPI
    remote_ip = request.client.host
    if remote_ip not in ALLOWED_IPS:
        # Block the request
        raise HTTPException(status_code=403, detail=f"Forbidden, not allowed")
    
    # Continue processing
    response = await call_next(request)
    return response


@app.post('/api/v1/store', response_model=RespStore)
async def store(req: ReqStore):
    file_id   = req.file_id
    file_name = req.file_name
    file_type = req.file_type

    db = get_current_async_dbc()
    
    rows = await db.read_async(
        table_name   = 'file_records',
        columns      = ['chunks'],
        where        = "file_id = %s",
        where_params = (req.file_id,),
        num          = 1
    )
    chunks = rows[0].get('chunks')

    IK.store_excerpts_to_kb_async(
        file_id   = file_id,
        file_name = file_name,
        file_type = file_type
    )
    
    return RespStore(
        status  = RespStatus.OK,
        message = f"chunks of [{req.file_name}, id = {file_id}] stored successfully."
    )


@app.post('/api/v1/remove', response_model=RespRemove)
async def remove(req: ReqRemove):
    file_id      = req.file_id
    total_chunks = req.total_chunks
    # doc_ids      = [f'{file_id}-{i}' for i in range(total_chunks)]

    IK.erase_excerpts_from_kb(file_id=file_id, total_excerpts=total_chunks)
    # K.remove_excerpts_from_kb(doc_ids=doc_ids)

    return RespRemove(
        status  = RespStatus.OK,
        message = f"chunks of [id = {file_id}] removed successfully."
    )


@app.post('/api/v1/retrieve', response_model=RespRetrieve)
async def retrieve_documents(req: ReqRetrieve):
    retrieved = IK.recall_k_excerpts(req.query, req.top_k)
    results = []
    
    for doc in retrieved:
        results.append(
            RetrievedDocument(
                id      = doc.id,
                score   = doc.score,
                source  = doc.meta.get('title'),
                page    = doc.meta.get('page_idx'),
                count   = doc.meta.get('count'),
                excerpt = doc.content.replace('\t\t', "")
            )
        )
    logger.info("Retrieved %d documents for query: %s", len(results), req.query)
    return RespRetrieve(
        query   = req.query,
        results = results
    )
    
    
@app.get('/api/v1/vkbase/search', response_model=RespRetrieve)
async def retrieve_documents(
    q: str = Query(..., description = "User query text"),
    k: int = Query(3, description   = "Number of documents to retrieve")
):
    retrieved = IK.recall_k_excerpts(q, k)

    results = []

    for doc in retrieved:
        results.append(
            RetrievedDocument(
                id      = doc.id,
                score   = doc.score,
                source  = doc.meta.get('title'),
                page    = doc.meta.get('page_idx'),
                count   = doc.meta.get('count'),
                excerpt = doc.content.replace('\t\t', "")
            )
        )

    logger.info(
        "Retrieved %d documents for query: %s",
        len(results),
        q
    )

    return RespRetrieve(
        query   = q,
        results = results
    )