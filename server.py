#!/usr/bin/env python3
# server.py

import subprocess
import os
import signal
import sys
import yaml
from datetime import datetime
from pathlib  import Path

LOGS_BASE_DIR     = 'logs'
LOGGING_YAML_PATH = './mdo/config/logging.yaml'
SERVICE_YAML_PATH = "./mdo/config/service.yaml"


def load_config():
    with open(SERVICE_YAML_PATH, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    default_host = os.getenv('DEFAULT_HOST')
    if default_host == '' or default_host is None:
        default_host = cfg['default_host'] 

    apps = []
    for name, app in cfg["apps"].items():
        apps.append({
            'name'   : name,
            'script' : app['script'],
            'host'   : app.get('host', default_host),
            'port'   : app['port'],
        })

    return apps


apps = load_config()


def get_timestamp():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def select_apps(names):
    """Return list of apps matching names. If names empty, return all."""
    if not names:
        return apps
    selected = [app for app in apps if app['name'] in names]
    missing = set(names) - set(app['name'] for app in selected)
    if missing:
        print(f"Warning: unknown app(s) {', '.join(missing)}")
    return selected


def launch_apps(selected_apps):
    for app in selected_apps:
        log_dir = os.path.join(LOGS_BASE_DIR, app['name'])
        os.makedirs(log_dir, exist_ok=True)
        timestamp = get_timestamp()
        log_path = os.path.join(log_dir, f"{app['name']}-{timestamp}.log")
        print(f"Starting {app['script']} on port {app['port']} -> logging to {log_path}")
        log_file = open(log_path, 'a')

        uvicorn_cmd = [
            "uv", "run", "--no-sync",
            "python", "-m", "uvicorn",
            app["script"].replace("/", ".").replace(".py", "") + ":app",
            "--host", app["host"],
            "--port", str(app["port"]),
            "--log-config", LOGGING_YAML_PATH
        ]

        if os.name == "nt":
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(
                uvicorn_cmd,
                stdout        = log_file,
                stderr        = log_file,
                creationflags = DETACHED_PROCESS
            )
        else:
            subprocess.Popen(
                uvicorn_cmd,
                stdout     = log_file,
                stderr     = log_file,
                preexec_fn = os.setpgrp
            )


def stop_apps(selected_apps):
    for app in selected_apps:
        port = app['port']
        if os.name == "nt":
            cmd = f'netstat -ano | findstr :{port}'
            result = subprocess.getoutput(cmd)
            if result:
                lines = result.strip().splitlines()
                for line in lines:
                    pid = line.split()[-1]
                    print(f"Killing PID {pid} on port {port}")
                    subprocess.call(f'taskkill /F /PID {pid}', shell=True)
            else:
                print(f"No process found on port {port}")
        else:
            cmd = f'lsof -ti:{port}'
            pids = subprocess.getoutput(cmd).strip().split()
            if pids and pids[0]:
                for pid in pids:
                    print(f"Killing PID {pid} on port {port}")
                    os.kill(int(pid), signal.SIGTERM)
            else:
                print(f"No process found on port {port}")
    print("Selected FastAPI apps stopped.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python server.py [start|stop] [app1 app2 ...]")
        sys.exit(1)

    command = sys.argv[1].lower()
    app_names = sys.argv[2:]  # optional list of apps
    selected_apps = select_apps(app_names)

    if command == "start":
        launch_apps(selected_apps)
    elif command == "stop":
        stop_apps(selected_apps)
    else:
        print("Unknown command. Use 'start' or 'stop'.")
        sys.exit(1)