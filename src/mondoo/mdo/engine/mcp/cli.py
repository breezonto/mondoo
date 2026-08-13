import socket
import json
import mondoo.mdo.engine.mcp.gateway

from mondoo.mdo.engine.configurator import SOCK_PATH_4_GATEWAY


def send(req):
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCK_PATH_4_GATEWAY)

    sock.send((json.dumps(req) + "\n").encode())

    buffer = ""
    while True:
        data = sock.recv(4096)
        if not data:
            break

        buffer += data.decode()

        if '\n\n' in buffer:
            line, _ = buffer.split('\n\n', 1)
            sock.close()
            return json.loads(line)


def connect_2_gateway():
    print("\nMCP client ready 🔧.")
    print("Commands:")
    print("  tools           → list all tools")
    print("  add a b         → call add tool")
    print("  exit            → quit\n")
    while True:
        cmd = input("> ").strip()
        if cmd == 'exit':
            break
        
        parts = cmd.split()

        if len(parts) > 0:
            action = parts[0]
            if action == 'call':
                print(send(
                    {
                        'cmd'    : action,
                        'target' : parts[1],
                        'args'   : { 'num': 5 }
                    }
                ))
            elif action == 'list_tools':
                print(send(
                    {
                        'cmd' : action
                    }
                ))


if __name__ == '__main__':
    connect_2_gateway()