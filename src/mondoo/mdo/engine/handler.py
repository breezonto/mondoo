from mcp.client.stdio         import stdio_client, StdioServerParameters
from mcp.client.session       import ClientSession
from mondoo.configurator import SOCK_PATH_4_GATEWAY, END_FRAME
from pathlib                  import Path

import asyncio
import json
import os
import logging
import sys


TOOLS = []

logger = logging.getLogger(__name__)


class GatewayHandler:
    def __init__(self, session: ClientSession):
        self.session = session

    async def handle(self, req: dict):
        cmd = req.get("cmd")

        if cmd == 'list_tools':
            return await self._list_tools()

        elif cmd == 'call':
            result = await self._call(req)
            if hasattr(result, 'content'):
                # typical MCP response: list of content blocks
                output = []
                for c in result.content:
                    if hasattr(c, 'text'):
                        output.append(c.text)
                    else:
                        output.append(str(c))

                result = '\n'.join(output)
            else:
                result = str(result)
            
            return result

        else:
            return { 'error': f"Unknown cmd: {cmd}"}

    # --- commands ---

    async def _list_tools(self):
        """Call gateway.list_all_tools"""
        result = await self.session.call_tool('list_all_tools', None)
        result = json.loads(result.content[0].text)
        return result

    async def _call(self, req: dict):
        """
        Call a tool via gateway using target = 'server.tool'
        """
        target = req.get('target')
        args   = req.get('args', {})

        if not target:
            return {'error': "Missing 'target'"}

        # call gateway tool
        # server, tool = target.split(".")

        result = await self.session.call_tool(
            'call',
            {
                'target'    : target,
                'arguments' : args
            }
        )
        return result


async def handler_wrapper(reader, writer, handler: GatewayHandler):
    while True:
        data = await reader.readline()
        if not data:
            break
        try:
            req = json.loads(data.decode())
            result = await handler.handle(req)
        except Exception as e:
            result = { 'error': str(e) }

        writer.write((json.dumps(result) + END_FRAME).encode())
        await writer.drain()

    writer.close()


def get_available_tools():
    global TOOLS
    return TOOLS


async def run_gateway():
    if os.path.exists(SOCK_PATH_4_GATEWAY):
        os.remove(SOCK_PATH_4_GATEWAY)
    
    gateway_script_path = os.path.join(Path(__file__).resolve().parent, '../../mcp/gateway.py')

    params = StdioServerParameters(
        command = sys.executable, 
        args    = [gateway_script_path],
        env     = os.environ.copy()
    )
    
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            handler = GatewayHandler(session)
            server = await asyncio.start_unix_server(
                lambda r, w: handler_wrapper(r, w, handler),
                path = SOCK_PATH_4_GATEWAY
            )
            logger.info("\"MCP Gateway Server Launched\"")
            async with server:
                await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(run_gateway())