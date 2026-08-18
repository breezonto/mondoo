from mondoo.configurator import get_global_config_value, SERVER_URL, ALLOWED_IPS
from .rr.ocr          import *

from fastapi  import FastAPI, HTTPException, Request

import mondoo.mdo.api.ocr as iocr

import logging
import os

logger = logging.getLogger(__name__)


logger.info(f"Proxy URLs: {SERVER_URL}")
logger.info(f"Allowed Incoming IPs: {ALLOWED_IPS}")


app = FastAPI(
    title       = 'OCR Service',
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
        raise HTTPException(status_code=403, detail=f"Forbidden: {remote_ip} not allowed")
    
    # Continue processing
    response = await call_next(request)
    return response
    
    
@app.post('/api/v1/ocr/recognize')
async def recognize(req : ReqRecognize):
    file_path     = req.file_path
    outputs, name = iocr.predict_in_structure(file_path=file_path)
    
    results = []
    for output in outputs:
        results.append(output.json)

    return RespRecognize(
        status  = RespStatus.OK,
        name    = name,
        results = results
    )