from mondoo.configurator import (END_FRAME, get_global_config_value)

from langgraph.graph import (
    StateGraph,
    MessagesState,
    START,
    END,
)

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
    ToolMessage,
)

from typing                  import AsyncGenerator, Any
from langchain_core.messages import HumanMessage
from langchain_core.tools    import StructuredTool
from langchain_deepseek      import ChatDeepSeek
from langgraph.prebuilt      import ToolNode

import time
import os
import asyncio
import json
import logging

SOCK_PATH_4_GATEWAY  = get_global_config_value('assets/sock_path_4_gateway')
SOCK_BUFFER_SIZE     = 4096


logger = logging.getLogger(__name__)


async def _execute_tool_async_(
    name: str,
    args: dict,
):
    """
    Execute a tool through the gateway.
    """

    reader, writer = await asyncio.open_unix_connection(
        SOCK_PATH_4_GATEWAY
    )

    try:
        req = {
            "cmd"    : "call",
            "target" : name,
            "args"   : args,
        }

        writer.write((json.dumps(req) + "\n").encode())

        await writer.drain()

        buffer = ""

        while True:
            data = await reader.read(SOCK_BUFFER_SIZE)

            if not data:
                raise RuntimeError(
                    f"Gateway closed connection "
                    f"while executing tool '{name}'"
                )

            buffer += data.decode()

            if END_FRAME in buffer:
                line, _ = buffer.split(END_FRAME, 1,)

                return json.loads(line)

    finally:
        writer.close()

        try:
            await writer.wait_closed()
        except Exception:
            pass


def _make_gateway_tool(
    name        : str,
    description : str,
    schema      : dict,
):
    """
    Create a LangChain tool that forwards execution
    to the gateway.
    """

    async def execute(**kwargs):
        return await _execute_tool_async_(
            name,
            kwargs,
        )

    return StructuredTool.from_function(
        coroutine   = execute,
        name        = name,
        description = description,
        args_schema = schema,
    )


async def _get_all_available_tools_():
    """
    Retrieve tool definitions from the gateway and convert
    them into LangChain StructuredTool objects.
    """

    reader, writer = await asyncio.open_unix_connection(SOCK_PATH_4_GATEWAY)

    try:
        req = {'cmd': 'list_tools', 'args': None}

        writer.write(
            (json.dumps(req) + "\n").encode()
        )

        await writer.drain()

        buffer = ""

        while True:
            data = await reader.read(SOCK_BUFFER_SIZE)

            if not data:
                raise RuntimeError(
                    "Gateway connection closed before "
                    "returning tool definitions"
                )

            buffer += data.decode()

            if END_FRAME in buffer:
                line, _ = buffer.split(
                    END_FRAME,
                    1,
                )

                desc = json.loads(line)

                break

    finally:
        writer.close()

        try:
            await writer.wait_closed()
        except Exception:
            pass

    tools = []

    for t in desc.get("tools", []):
        tools.append(
            _make_gateway_tool(
                name        = t["name"],
                description = t.get( "description") or "",
                schema      = t["schema"],
            )
        )

    return tools


def convert_messages(messages : list[dict[str, Any]]) -> list[BaseMessage]:

    result: list[BaseMessage] = []

    for message in messages:
        role = message['role']
        content = message.get('content', "")

        if role == 'user':
            result.append(
                HumanMessage(content = content)
            )

        elif role == 'assistant':
            result.append(
                AIMessage(
                    content    = content,
                    tool_calls = message.get('tool_calls', []),
                )
            )

        elif role == 'system':
            result.append(
                SystemMessage(content=content)
            )

        elif role == 'tool':
            result.append(
                ToolMessage(
                    content      = content,
                    tool_call_id = message['tool_call_id'],
                )
            )

        else:
            raise ValueError(
                f"Unknown message role: {role}"
            )

    return result


async def build_chat_graph():
    """
    """
    
    # tools cannot be hot-reload yet
    tools = await _get_all_available_tools_()

    llm = ChatDeepSeek(
        model       = 'deepseek-chat',
        temperature = 0,
        api_key     = os.getenv('DEEPSEEK_API_KEY'),
    )

    llm_with_tools = llm.bind_tools(tools)

    async def chatbot_node(
        state: MessagesState,
    ):
        response = await llm_with_tools.ainvoke(
            state['messages']
        )

        return {
            'messages': [response]
        }

    def should_continue(
        state: MessagesState,
    ):
        last_message = state['messages'][-1]

        if last_message.tool_calls:
            return 'tools'

        return END

    tool_node = ToolNode(tools)

    builder = StateGraph(MessagesState)

    builder.add_node('chatbot', chatbot_node)
    builder.add_node('tools', tool_node)

    builder.add_edge(START, 'chatbot')
    builder.add_conditional_edges(
        'chatbot',
        should_continue,
        {
        #   result  : next node
            'tools' : 'tools',
            END     : END,
        },
    )
    builder.add_edge('tools', 'chatbot')

    return builder.compile()


async def stream_response_in_messages_with_tool(
    messages   : list[dict],
    opts       : dict,
    model_type : str,
    context_id : str | None = None,
    time_out   : int = 20,
) -> AsyncGenerator[dict, None]:
    
    graph = await build_chat_graph()

    langchain_messages = convert_messages(messages)

    config = {
        "configurable": {
            "thread_id": context_id
        }
    }

    async for message, metadata in graph.astream(
        {
            "messages": langchain_messages
        },
        config      = config,
        stream_mode = 'messages',
    ):

        # Ignore tool messages
        if message.type != "AIMessageChunk":
            continue

        if not message.content:
            continue

        yield {
            "id"         : None,
            "object"     : "chat.completion.chunk",
            "created"    : int(time.time()),
            "model_type" : model_type,

            "usage" : {
                "prompt_tokens"            : None,
                "completion_tokens"        : None,
                "total_tokens"             : None,
                "token_generation_speed"   : None,
                "prompt_tokens_details"    : None,
                "prompt_cache_hit_tokens"  : 0,
                "prompt_cache_miss_tokens" : 0,
            },

            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": message.content,
                    },
                    "finish_reason": None,
                }
            ],
        }