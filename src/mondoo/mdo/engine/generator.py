from mondoo.configurator import (
    API_ENDPOINT,
    END_FRAME,
    get_global_config_value
)

from .manager.message_history import MsgHistoryManager

from fastapi    import HTTPException
from typing     import AsyncGenerator, List, Optional
from subprocess import Popen

import asyncio
import os
import httpx
import json
import logging


logger = logging.getLogger(__name__)

LOCAL_LLM_MODEL_PATH = get_global_config_value('assets/default_local_llm_path')
ENABLE_LOCAL_LLM     = get_global_config_value('assets/enable_local_llm')
SOCK_PATH_4_GATEWAY  = get_global_config_value('assets/sock_path_4_gateway')
SOCK_BUFFER_SIZE     = 4096

if ENABLE_LOCAL_LLM:
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    
    MODEL          = None
    TOKENIZER      = None
    LOCAL_PIPELINE = None

    def load_local_model():
        global TOKENIZER, MODEL, LOCAL_PIPELINE
        TOKENIZER = AutoTokenizer.from_pretrained(LOCAL_LLM_MODEL_PATH)
        MODEL = AutoModelForCausalLM.from_pretrained(LOCAL_LLM_MODEL_PATH, device_map="cuda")
        LOCAL_PIPELINE = pipeline("text-generation", model=MODEL, tokenizer=TOKENIZER)

    Popen(["llama-server", "-m", os.getenv('GGUF_PATH'), "--port", "8080"], shell=False)

    def start_llama_server():
        Popen([
            "llama-server", 
            "-m", os.getenv('GGUF_PATH'), "--port", "8080"
            ], 
            shell=False
        )

    start_llama_server()


logger.info(f"Local LLM Inference is {'enabled' if ENABLE_LOCAL_LLM else 'disabled'}")


def _convert_2_deepseek_tool_spec_(desc):
    """
    @TODO comment
    """

    result = []
    for t in desc['tools']:
        result.append({
            'type': 'function',
            'function' : {
                'name'        : t['name'],
                'description' : t['description'] or "",
                'parameters'  : t['schema']
            }
        })

    return result


async def _get_all_available_tools_():
    """
    @TODO comment
    """

    reader, writer = await asyncio.open_unix_connection(SOCK_PATH_4_GATEWAY)
    req = { 'cmd': 'list_tools', 'args': None }
    writer.write((json.dumps(req) + '\n').encode())

    await writer.drain()

    buffer = ""
    while True:
        data = await reader.read(SOCK_BUFFER_SIZE)
        if not data:
            break

        buffer += data.decode()

        if END_FRAME in buffer:
            line, _ = buffer.split(END_FRAME, 1)
            writer.close()
            await writer.wait_closed()
            tools = json.loads(line)
            return _convert_2_deepseek_tool_spec_(tools)    
        


async def execute_tool_async(name: str, args: dict):
    """
    @TODO comment
    """
    reader, writer = await asyncio.open_unix_connection(SOCK_PATH_4_GATEWAY)

    req = { 'cmd': 'call', 'target': name, 'args': args }
    
    writer.write((json.dumps(req) + '\n').encode())
    await writer.drain()

    buffer = ""
    while True:
        data = await reader.read(SOCK_BUFFER_SIZE)
        if not data:
            break

        buffer += data.decode()

        if END_FRAME in buffer:
            line, _ = buffer.split(END_FRAME, 1)
            writer.close()
            await writer.wait_closed()
            return json.loads(line)


async def response_in_message_with_tool(
    messages   : List[dict], 
    opts       : dict, 
    model_type : str,
    time_out   : int = 200
) -> str:
    """
    @TODO comment
    """

    API_KEY = None
    headers = dict()

    if model_type == 'remote':
        api_url = API_ENDPOINT['remote']
        API_KEY = os.getenv('DEEPSEEK_API_KEY')
        if not API_KEY:
            raise HTTPException(status_code=500, detail="API_KEY not set")
        headers['Authorization'] = f'Bearer {API_KEY}'
    else:
        api_url = API_ENDPOINT['local']

    headers['Content-Type'] = 'application/json'

    async with httpx.AsyncClient(timeout=time_out) as client:
        while True:
            payload = {
                'model'             : 'deepseek-chat' if model_type == 'remote' else 'local-chat-model',
                'messages'          : messages,
                'tools'             : await _get_all_available_tools_(),
                'max_tokens'        : opts['max_tokens'],
                'stream'            : False,
                'temperature'       : opts['temperature'],
                'frequency_penalty' : opts['repetition_penalty'],
                'top_p'             : opts['top_p'],
                # "top_k": opts.top_k,
            }

            resp = await client.post(api_url, headers=headers, json=payload)

            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)

            data = resp.json()
            message = data['choices'][0]['message']
            
            messages.append(message)

            if 'tool_calls' in message and message['tool_calls']:
                for tool_call in message['tool_calls']:
                    name = tool_call['function']['name']
                    args = tool_call['function']['arguments']

                    if isinstance(args, str):
                        args = json.loads(args)

                    result = await execute_tool_async(name, args)
                    
                    messages.append({
                        'role'         : 'tool', 
                        'tool_call_id' : tool_call['id'], 
                        'content'      : result
                    })

                continue

            return data


async def stream_response_in_messages_with_tool(
    messages   : List[dict], 
    opts       : dict,
    model_type : str,
    history_id : Optional[str] = None,
    time_out   : int = 20
) -> AsyncGenerator[dict, None]:
    """
    @TODO comment
    """

    API_KEY = None
    headers = {}

    _messages = messages.copy()

    if model_type == 'remote':
        api_url = API_ENDPOINT['remote']
        API_KEY = os.getenv('DEEPSEEK_API_KEY')
        if not API_KEY:
            raise HTTPException(status_code=500, detail="API_KEY not set")
        headers['Authorization'] = f'Bearer {API_KEY}'
    else:
        api_url = API_ENDPOINT['local']

    headers['Content-Type'] = 'application/json'

    async with httpx.AsyncClient(timeout=time_out) as client:

        while True:
            payload = {
                'model'       : 'deepseek-chat' if model_type == 'remote' else 'local-chat-model',
                'messages'    : _messages,
                'tools'       : await _get_all_available_tools_(),
                'max_tokens'  : opts['max_tokens'],
                'temperature' : opts['temperature'],
                'stream'      : True,
                'top_p'       : opts['top_p'],
            }

            tool_calls_buffer = []
            content = ""

            async with client.stream('POST', api_url, headers=headers, json=payload) as response:

                async for line in response.aiter_lines():
                    if not line.startswith('data: '):
                        continue

                    content_in_event = line[len('data: '):]

                    if content_in_event == '[DONE]':
                        break

                    chunk = json.loads(content_in_event)
                    choice = chunk['choices'][0]
                    delta = choice.get('delta', {})

                    if 'content' in delta and delta['content']:
                        content += delta['content']

                        usage = {
                            'prompt_tokens'            : None,
                            'completion_tokens'        : None,
                            'total_tokens'             : None,
                            'token_generation_speed'   : None,
                            'prompt_tokens_details'    : None,
                            'prompt_cache_hit_tokens'  : 0,
                            'prompt_cache_miss_tokens' : 0
                        }

                        yield {
                            'id'         : chunk.get('id'),
                            'object'     : chunk.get('object'),
                            'created'    : chunk.get('created'),
                            'model_type' : model_type,
                            'usage'      : usage,
                            'choices'    : [{
                                'index'         : 0,
                                'message'       : { 'role': 'assistant', 'content': delta['content'] },
                                'finish_reason' : None
                            }],
                        }

                    if 'tool_calls' in delta:
                        for tc in delta['tool_calls']:
                            if len(tool_calls_buffer) <= tc['index']:
                                tool_calls_buffer.append(tc)
                            else:
                                tool_calls_buffer[tc['index']]['function']['arguments'] += \
                                    tc['function'].get('arguments', "")

                    finish_reason = choice.get('finish_reason')

                    if finish_reason == 'tool_calls':
                        break

            if tool_calls_buffer:
                _messages.append({
                    'role'       : 'assistant',
                    'content'    : content,
                    'tool_calls' : tool_calls_buffer
                })

                if history_id is not None:
                    MsgHistoryManager.push_message(
                        history_id,
                        message= { 
                            'role'       : 'assistant', 
                            'content'    : content, 
                            'tool_calls' : tool_calls_buffer 
                        }
                    )
                
                for tool_call in tool_calls_buffer:
                    name = tool_call['function']['name']
                    args = tool_call['function']['arguments']

                    if isinstance(args, str):
                        args = json.loads(args)

                    result = await execute_tool_async(name, args)

                    _messages.append({
                        'role'         : 'tool',
                        'tool_call_id' : tool_call['id'],
                        'content'      : result
                    })

                    if history_id is not None:
                        MsgHistoryManager.push_message(
                            history_id,
                            message= { 
                                'role'         : 'tool', 
                                'content'      : content, 
                                'tool_call_id' : tool_call['id'],
                            }
                        )

                continue

            else:
                _messages.append({
                    'role'    : 'assistant',
                    'content' : content
                })

                if history_id is not None:
                    MsgHistoryManager.push_message(
                        history_id,
                        message= { 
                            'role'    : 'assistant', 
                            'content' : content
                        }
                    )
                break



async def query_message_history(history_id : str):
    """
    @TODO comment
    """

    return MsgHistoryManager.query_messages(history_id)