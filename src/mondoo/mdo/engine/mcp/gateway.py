# --- gateway.py ---
import asyncio
import anyio
import logging
import logging.config
import json
import sys

from mcp.server.fastmcp       import FastMCP
from mcp.client.session       import ClientSession
from mcp.client.stdio         import stdio_client, StdioServerParameters
from mondoo.mdo.engine.configurator import SOCK_PATH_4_KALEIDO, SOCK_PATH_4_META
from mondoo.mdo.core.common         import setup_mcp_logging


config = setup_mcp_logging('gateway')
logging.config.dictConfig(config)
logger = logging.getLogger('mdo.engine.mcp.gateway')


mcp = FastMCP('gateway')


def get_deepseek_spec(desc):
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



def get_help_spec(tools):
    result = []
    for t in tools.tools:
        result.append(
            {
                'name'   : t.name,
                'desc'   : t.description,
                'params' : t.inputSchema 
            }
        )


async def handle_client(reader, writer, session: ClientSession):
    while True:
        data = await reader.readline()
        if not data:
            break

        req = json.loads(data.decode())
        cmd = req.get('cmd')
        
        tools      = await session.list_tools()
        tool_names = [t.name for t in tools.tools]
        try:
            if cmd == 'tools':
                # tools = await session.list_tools()
                result = tool_names

            elif cmd in tool_names:
                result = await session.call_tool(cmd, req.get("args", {}))

            else:
                result = {'error': f"unknown command: {cmd}"}

        except Exception as e:
            result = { 'error': str(e) }

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

        resp = json.dumps(result) + '\n\n'
        writer.write(resp.encode())
        await writer.drain()

    writer.close()


class MCPGateway:
    def __init__(self):
        self.sessions  = {}
        self._ready    = {}
        self._tasks    = {}
        self._errors   = {}          # ← capture why each server died

    async def connect_server(self, name: str, command: list[str], sock_path) -> None:
        """Connect to an MCP server and block until it's ready."""
        if name in self._tasks:
            raise RuntimeError(f"Server '{name}' is already registered")

        ready_event = asyncio.Event()       # <-- signals readiness
        self._ready[name] = False

        async def _runner():
            cmd  = command[0]
            args = command[1:]

            params = StdioServerParameters(
                command=cmd,
                args=args,
            )

            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    # Initialize the session (handshake with server)
                    await session.initialize()
                    self.sessions[name] = session

                    self._ready[name] = True
                    ready_event.set()

                    server = await asyncio.start_unix_server(
                        lambda r, w: handle_client(r, w, session),
                        path = sock_path
                    )
                    
                    async with server:
                        await server.serve_forever()


        self._tasks[name] = asyncio.create_task(_runner())

        # Block the caller until the session is initialized
        await ready_event.wait()


    async def list_all_tools(self):
        """Aggregate tools from all servers"""
        domains = {}

        for name, session in self.sessions.items():
            try:
                tools = await session.list_tools()
                domains[name] = [
                    {
                        'name'        : t.name,
                        'description' : t.description,
                        'schema'      : t.inputSchema,
                    }
                    for t in tools.tools
                ]
            except Exception as e:
                domains[name] = f"ERROR: {str(e)}"

            
        return domains

    async def call_tool(self, server: str, tool: str, args: dict):
        if server not in self.sessions:
            return f"Server '{server}' not found"

        if not self._ready.get(server):
            err = self._errors.get(server, "unknown reason")
            return f"Server '{server}' is dead: {err}"

        session = self.sessions[server]

        try:
            result = await session.call_tool(tool, args)
            return result
        except Exception as e:
            return f"Call failed: {type(e).__name__}: {e}"


gateway = MCPGateway()


# lifecycle management
async def startup():
    await gateway.connect_server('kaleido', 
        command = [
            sys.executable,
            "-m",
            'mdo.engine.mcp.server.kaleidoscope'
        ],
        sock_path = SOCK_PATH_4_KALEIDO
    )
    logger.info("Gateway Connected to Server: Kaleido")
    
    await gateway.connect_server('meta', 
        command   = [
            sys.executable,
            "-m",
            'mdo.engine.mcp.server.meta'
        ],
        sock_path = SOCK_PATH_4_META
    )
    logger.info("Gateway Connected to Server: Meta")


@mcp.tool()
async def list_all_tools() -> dict:
    """List all tools from all MCP servers"""
    domains = await gateway.list_all_tools()
    result = []
    for domain_name, tool_specs in domains.items():
        for tool_spec in tool_specs:
            result.append({
                'name'        : '-'.join([domain_name, tool_spec['name']]),
                'description' : tool_spec['description'],
                'schema'      : tool_spec['schema'],
            })

    result = { 'tools': result }
    return result


@mcp.tool()
async def call(
    target: str,
    arguments: dict
):
    """
    target format: "server-tool"
    """
    try:
        server, tool = target.split('-', 1)
    except ValueError:
        return {"error": f"Invalid target: {target}"}

    return await gateway.call_tool(server, tool, arguments)


async def main():
    await startup()
    await mcp.run_stdio_async()


if __name__ == '__main__':
    anyio.run(main)