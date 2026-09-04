from mondoo.mdo.engine.handler    import run_gateway
from mondoo.mdo.api.chatbot       import SYSTEM_PROMPT_DEFAULT
from mondoo.mdo.generator.vanilla import (
    response_in_message_with_tool,
    query_message_history
)

from mondoo.service.rr.chat import (
    Role, Message, Usage, Choice,
    ReqChatCompletion,
    RespChatCompletionNoStream
)

from contextlib        import asynccontextmanager
from fastapi           import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pathlib           import Path

import mondoo.mdo.generator.lg as L

import time
import json
import asyncio
import logging
import os


logger = logging.getLogger(__name__)

SERVER_URL = os.getenv('PROXY_URL', None)
logger.info(f"Proxy URLs: {SERVER_URL}")

ALLOWED_IPS = os.getenv('ALLOWED_INCOMING_IPS', '127.0.0.1')
logger.info(f"Allowed Incoming IPs: {ALLOWED_IPS}")


PSQL_HOST = os.getenv('PSQL_HOST', None)
PSQL_PORT = os.getenv('PSQL_PORT', None)
PSQL_DB   = os.getenv('PSQL_DB', None)
logger.info(f"PostgreSQL Connection: {PSQL_HOST}:{PSQL_PORT}@{PSQL_DB}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [
        asyncio.create_task(run_gateway())
    ]

    try:
        yield
    finally:
        for task in tasks:
            task.cancel()

        await asyncio.gather(*tasks, return_exceptions=True)
        print("All workers stopped")


app = FastAPI(
    title       = 'chat',
    servers     = [
        {
            'url': SERVER_URL, 
            'description': "Nginx reverse proxy path"
        }
    ],
    lifespan    = lifespan,
    docs_url    = '/docs',
    redoc_url   = '/redoc',
    openapi_url = '/openapi.json'
)


async def json_streamer(generator):
    async for json_object in generator:
        yield json.dumps(json_object, ensure_ascii = False) + '\n'


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


@app.post('/api/v1/chat/completions')
async def chat_completion(req: ReqChatCompletion):
    opts       = req.options.model_dump()
    stream_gen = None
    resp       = None
    elapsed    = 0.0

    if len(req.messages) < 1: # messages is empty
        HTTPException(status_code=422, detail="Messages Should Not Be Empty!")

    messages = req.messages

    # if req.context_id is None:
    #     if messages[0].role != Role.SYSTEM:
    #         message = Message(
    #             role    = Role.SYSTEM,
    #             content = SYSTEM_PROMPT_DEFAULT 
    #         )
    #         messages.insert(0, message)
    #         logger.info("\"\nSystem Prompt Not Set. Using Default System Prompt:\n %s\n\"", SYSTEM_PROMPT_DEFAULT)
    #     else:
    #         logger.info("\"\nFrontend Set System Prompt:\n %s\n\"", messages[0].content)

    message_dicts = []
    
    for message in messages:
        message_dicts.append(message.model_dump())

    if req.options.stream:
        stream_gen = L.stream_response_in_messages_with_tool(
            messages   = message_dicts, 
            opts       = opts, 
            model_type = req.model_type, 
            context_id = req.context_id
        )
        return StreamingResponse(json_streamer(stream_gen), media_type='text/json')

    start     = time.perf_counter()
    resp      = await response_in_message_with_tool(message_dicts, opts, req.model_type)
    end       = time.perf_counter()
    elapsed   = end - start

    text = ""
    if 'choices' in resp and len(resp['choices']) > 0:
        choice = resp['choices'][0]
        if 'message' in choice and 'content' in choice['message']:
            text = choice['message']['content']
        elif 'text' in choice:
            text = choice['text']            

    prompt_tokens          = resp.get('usage', {}).get('prompt_tokens', 0)
    completion_tokens      = resp.get('usage', {}).get('completion_tokens', 0)
    total_tokens           = resp.get('usage', {}).get('total_tokens', 0)
    token_generation_speed = -1
    
    if req.model_type == 'local':
        token_generation_speed = resp.get('timings', {}).get('predicted_per_second', None)
    elif req.model_type == 'remote':
        token_generation_speed = total_tokens / elapsed if elapsed > 0 else None
    
    usage = Usage(
        prompt_tokens          = prompt_tokens,
        completion_tokens      = completion_tokens,
        total_tokens           = total_tokens,
        token_generation_speed = token_generation_speed
    )
    
    choice = Choice(
        index         = 0,
        message       = Message(role = Role.ASSISTANT, content = text),
        finish_reason = 'stop'
    )

    response = RespChatCompletionNoStream(
        id                 = f'chatcmpl-{int(time.time()*1000)}',
        object             = 'chat.completion',
        created            = int(time.time()),
        model_type         = req.model_type,
        choices            = [choice],
        usage              = usage,
        system_fingerprint = None
    )

    return response


@app.get('/api/v1/chat/{history_id}')
def get_message_history(history_id : str):
    return query_message_history(history_id)